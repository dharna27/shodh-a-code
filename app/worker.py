import os,time,uuid,logging
from datetime import datetime,timedelta,timezone
import httpx
from sqlalchemy import select,or_
from .db import SessionLocal
from .models import Attempt,Submission,TestCase
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
RUNNER=os.getenv("RUNNER_URL","http://runner:8080")
TOKEN=os.getenv("RUNNER_TOKEN","local_runner_token")


def finalize_exhausted_attempts():
    """Mark expired attempts with exhausted retries as failed."""
    with SessionLocal.begin() as db:
        now = datetime.now(timezone.utc)

        stmt = (
            select(Attempt)
            .where(
                Attempt.state == "running",
                Attempt.retries >= 3,
                Attempt.lease_until < now
            )
            .with_for_update(skip_locked=True)
        )

        attempts = db.scalars(stmt).all()

        for attempt in attempts:
            attempt.state = "failed"
            attempt.verdict = "judge_failure"
            attempt.completed_at = now
            attempt.lease_until = None
            attempt.claim_token = None

            logging.warning(
                "attempt_retry_exhausted attempt_id=%s retries=%s",
                attempt.id,
                attempt.retries
            )

        return len(attempts)

def claim():
    with SessionLocal.begin() as db:
        now=datetime.now(timezone.utc)
        stmt=(select(Attempt).where(or_(Attempt.state=="queued",(Attempt.state=="running")&(Attempt.lease_until<now))).where(Attempt.retries<3).order_by(Attempt.id).with_for_update(skip_locked=True).limit(1))
        a=db.scalar(stmt)
        if not a:return None
        a.state="running";a.retries+=1;a.claim_token=str(uuid.uuid4());a.lease_until=now+timedelta(seconds=45)
        return a.id,a.claim_token

def run_once():
    job=claim()
    if not job:return False
    aid,token=job
    with SessionLocal() as db:
        a=db.get(Attempt,aid);s=db.get(Submission,a.submission_id)
        cases=db.scalars(select(TestCase).where(TestCase.suite_id==a.suite_id).order_by(TestCase.id)).all()
        payload={"code":s.code,"cases":[{"input":x.input,"expected":x.expected} for x in cases]}
    try:
        response=httpx.post(RUNNER+"/execute",json=payload,headers={"X-Runner-Token":TOKEN},timeout=35)
        response.raise_for_status();verdict=response.json()["verdict"]
        if verdict not in ("accepted","wrong_answer","runtime_error","time_limit","output_limit","compilation_error","judge_failure"):
            raise ValueError("Invalid runner verdict")
    except Exception:
        logging.exception("judge_infrastructure_failure attempt_id=%s",aid)
        verdict="judge_failure"
    with SessionLocal.begin() as db:
        a=db.get(Attempt,aid)
        if a.claim_token!=token or a.state!="running":return True
        if verdict=="judge_failure" and a.retries<3:
            a.state="queued";a.lease_until=None
        else:
            a.state="failed" if verdict=="judge_failure" else "completed"
            a.verdict=verdict;a.completed_at=datetime.now(timezone.utc)
        logging.info("attempt_finalized attempt_id=%s submission_id=%s verdict=%s",aid,a.submission_id,verdict)
    return True


if __name__ == "__main__":
    while True:
        try:
            finalize_exhausted_attempts()

            if not run_once():
                time.sleep(0.5)

        except Exception:
            logging.exception("worker error")
            time.sleep(2)


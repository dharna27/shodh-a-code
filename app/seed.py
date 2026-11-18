from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from .db import SessionLocal
from .models import User, Organization, Membership, Contest, Problem, ProblemVersion, TestSuite, TestCase

def seed():
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).limit(1)): return
        for name in ("alice", "bob", "olivia", "mallory"):
            db.add(User(name=name))
        for name in ("Alpha", "Beta"):
            db.add(Organization(name=name))
        db.flush()
        db.add_all([Membership(user_id=1,org_id=1,role="organizer"),Membership(user_id=2,org_id=1,role="participant"),Membership(user_id=3,org_id=2,role="organizer"),Membership(user_id=4,org_id=2,role="participant")])
        now=datetime.now(timezone.utc)
        for org in (1,2):
            contest=Contest(org_id=org,title=f"Org {org} Demo Contest",starts_at=now-timedelta(days=1),ends_at=now+timedelta(days=7))
            db.add(contest);db.flush()
            for title,inp,out in (("Add two integers","2 3\n","5"),("Double integer","4\n","8")) if org==1 else (("Square integer","3\n","9"),):
                problem=Problem(contest_id=contest.id,title=title);db.add(problem);db.flush()
                pv=ProblemVersion(problem_id=problem.id,version=1,statement=title);db.add(pv);db.flush()
                suite=TestSuite(problem_version_id=pv.id,version=1);db.add(suite);db.flush()
                db.add(TestCase(suite_id=suite.id,input=inp,expected=out,hidden=True))
if __name__=="__main__": seed()

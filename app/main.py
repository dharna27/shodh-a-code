import os
import hmac
import hashlib, json
from datetime import datetime, timezone
from typing import Annotated
from fastapi import FastAPI, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Membership, Contest, Participation, Problem, ProblemVersion, TestSuite, Submission, Attempt

app=FastAPI(title="Shodh a Code",version="0.1.0",description="Development identity fixture: X-User-ID header")

def actor(
    x_user_id: Annotated[int, Header(alias="X-User-ID")],
    x_dev_token: Annotated[str, Header(alias="X-Dev-Token")],
    db: Session = Depends(get_db),
):
    secret = os.environ.get("DEV_AUTH_SECRET")
    if not secret:
        raise HTTPException(503, "Development authentication not configured")

    expected = hmac.new(
        secret.encode(),
        f"user:{x_user_id}".encode(),
        "sha256",
    ).hexdigest()

    if not hmac.compare_digest(x_dev_token, expected):
        raise HTTPException(401, "Invalid development credentials")

    user = db.get(User, x_user_id)
    if not user:
        raise HTTPException(401, "Unknown development identity")

    return user

def membership(db, user_id, org_id, organizer=False):
    m=db.scalar(select(Membership).where(Membership.user_id==user_id,Membership.org_id==org_id))
    if not m: raise HTTPException(403,"Not a member of this organization")
    if organizer and m.role!="organizer": raise HTTPException(403,"Organizer role required")
    return m

def contest_access(db,cid,user,organizer=False):
    c=db.get(Contest,cid)
    if not c: raise HTTPException(404,"Contest not found")
    membership(db,user.id,c.org_id,organizer)
    return c

class ContestCreate(BaseModel):
    title:str=Field(min_length=1,max_length=120)
    starts_at:datetime
    ends_at:datetime
class SubmitBody(BaseModel):
    problem_id:int
    code:str=Field(min_length=1,max_length=50000)
    language:str="python3"
class RejudgeBody(BaseModel):
    suite_id:int

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/contests")
def list_contests(limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),db:Session=Depends(get_db),user:User=Depends(actor)):
    org_ids=select(Membership.org_id).where(Membership.user_id==user.id)
    rows=db.scalars(select(Contest).where(Contest.org_id.in_(org_ids)).order_by(Contest.id).offset(offset).limit(limit)).all()
    return [{"id":c.id,"title":c.title,"org_id":c.org_id,"starts_at":c.starts_at,"ends_at":c.ends_at} for c in rows]

@app.post("/organizations/{org_id}/contests",status_code=201)
def create_contest(org_id:int,body:ContestCreate,db:Session=Depends(get_db),user:User=Depends(actor)):
    membership(db,user.id,org_id,True)
    if body.starts_at>=body.ends_at: raise HTTPException(422,"starts_at must precede ends_at")
    c=Contest(org_id=org_id,**body.model_dump());db.add(c);db.commit();db.refresh(c)
    return {"id":c.id}

@app.get("/contests/{contest_id}/problems")
def problems(contest_id:int,db:Session=Depends(get_db),user:User=Depends(actor)):
    contest_access(db,contest_id,user)
    rows=db.scalars(select(Problem).where(Problem.contest_id==contest_id).order_by(Problem.id)).all()
    return [{"id":p.id,"title":p.title} for p in rows]

@app.post("/contests/{contest_id}/join")
def join(contest_id:int,db:Session=Depends(get_db),user:User=Depends(actor)):
    c=contest_access(db,contest_id,user)
    now=datetime.now(timezone.utc)
    if not c.starts_at<=now<c.ends_at: raise HTTPException(409,"Contest not open")
    existing=db.scalar(select(Participation).where(Participation.contest_id==contest_id,Participation.user_id==user.id))
    if existing: return {"participation_id":existing.id}
    part=Participation(contest_id=contest_id,user_id=user.id);db.add(part)
    try: db.commit()
    except IntegrityError:
        db.rollback();part=db.scalar(select(Participation).where(Participation.contest_id==contest_id,Participation.user_id==user.id))
    return {"participation_id":part.id}

@app.post("/contests/{contest_id}/submissions",status_code=202)
def submit(contest_id:int,body:SubmitBody,idempotency_key:Annotated[str,Header(alias="Idempotency-Key",min_length=1,max_length=120)],db:Session=Depends(get_db),user:User=Depends(actor)):
    c=contest_access(db,contest_id,user)
    if body.language!="python3": raise HTTPException(422,"Only python3 is supported")
    payload=body.model_dump();digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    existing=db.scalar(select(Submission).where(Submission.contest_id==contest_id,Submission.user_id==user.id,Submission.idem_key==idempotency_key))
    if existing:
        if existing.request_hash!=digest: raise HTTPException(409,"Idempotency key reused with different request")
        return {"submission_id":existing.id,"attempt_id":existing.current_attempt_id,"replayed":True}
    now=datetime.now(timezone.utc)
    if not c.starts_at<=now<c.ends_at: raise HTTPException(409,"Contest not open")
    part=db.scalar(select(Participation.id).where(Participation.contest_id==contest_id,Participation.user_id==user.id))
    if not part: raise HTTPException(403,"Join contest before submitting")
    problem=db.get(Problem,body.problem_id)
    if not problem or problem.contest_id!=contest_id: raise HTTPException(404,"Problem not in contest")
    pv=db.scalar(select(ProblemVersion).where(ProblemVersion.problem_id==problem.id).order_by(ProblemVersion.version.desc()))
    suite=db.scalar(select(TestSuite).where(TestSuite.problem_version_id==pv.id).order_by(TestSuite.version.desc()))
    if not suite: raise HTTPException(409,"Problem has no test suite")
    s=Submission(contest_id=contest_id,user_id=user.id,problem_id=problem.id,problem_version_id=pv.id,suite_id=suite.id,code=body.code,language=body.language,runtime={"wall_seconds":3,"memory_mb":128},idem_key=idempotency_key,request_hash=digest)
    db.add(s)
    try:
        db.flush();a=Attempt(submission_id=s.id,suite_id=suite.id);db.add(a);db.flush();s.current_attempt_id=a.id;db.commit()
    except IntegrityError:
        db.rollback()
        existing=db.scalar(select(Submission).where(Submission.contest_id==contest_id,Submission.user_id==user.id,Submission.idem_key==idempotency_key))
        if not existing: raise
        if existing.request_hash!=digest: raise HTTPException(409,"Idempotency key reused with different request")
        return {"submission_id":existing.id,"attempt_id":existing.current_attempt_id,"replayed":True}
    return {"submission_id":s.id,"attempt_id":a.id,"replayed":False}

@app.get("/submissions/{submission_id}")
def submission_status(submission_id:int,db:Session=Depends(get_db),user:User=Depends(actor)):
    s=db.get(Submission,submission_id)
    if not s: raise HTTPException(404,"Submission not found")
    contest_access(db,s.contest_id,user)
    if s.user_id!=user.id:
        c=db.get(Contest,s.contest_id);membership(db,user.id,c.org_id,True)
    a=db.get(Attempt,s.current_attempt_id)
    return {"id":s.id,"contest_id":s.contest_id,"problem_id":s.problem_id,"problem_version_id":s.problem_version_id,"test_suite_id":s.suite_id,"state":a.state,"verdict":a.verdict,"attempt_id":a.id}

@app.post("/submissions/{submission_id}/rejudge",status_code=202)
def rejudge(submission_id:int,body:RejudgeBody,db:Session=Depends(get_db),user:User=Depends(actor)):
    s=db.get(Submission,submission_id)
    if not s: raise HTTPException(404,"Submission not found")
    contest_access(db,s.contest_id,user,True)
    suite=db.get(TestSuite,body.suite_id)
    if not suite: raise HTTPException(404,"Test suite not found")
    pv=db.get(ProblemVersion,suite.problem_version_id)
    if pv.problem_id!=s.problem_id: raise HTTPException(409,"Test suite belongs to another problem")
    a=Attempt(submission_id=s.id,suite_id=suite.id)
    db.add(a);db.flush();s.current_attempt_id=a.id;db.commit()
    return {"attempt_id":a.id}

@app.get("/contests/{contest_id}/leaderboard")
def leaderboard(contest_id:int,db:Session=Depends(get_db),user:User=Depends(actor)):
    contest_access(db,contest_id,user)
    parts=db.scalars(select(Participation).where(Participation.contest_id==contest_id)).all()
    result=[]
    for part in parts:
        subs=db.scalars(select(Submission).where(Submission.contest_id==contest_id,Submission.user_id==part.user_id).order_by(Submission.created_at,Submission.id)).all()
        by_problem={}
        for s in subs:
            a=db.get(Attempt,s.current_attempt_id)
            if not a or a.state!="completed":continue
            x=by_problem.setdefault(s.problem_id,{"wrong":0,"solved":False,"penalty":0})
            if x["solved"]:continue
            if a.verdict=="accepted":
                x["solved"]=True
                c=db.get(Contest,contest_id)
                minutes=max(0,int((s.created_at-c.starts_at).total_seconds()//60))
                x["penalty"]=minutes+20*x["wrong"]
            elif a.verdict in ("wrong_answer","runtime_error","time_limit","compilation_error","output_limit"):
                x["wrong"]+=1
        solved=sum(x["solved"] for x in by_problem.values())
        penalty=sum(x["penalty"] for x in by_problem.values() if x["solved"])
        result.append({"user_id":part.user_id,"solved":solved,"penalty":penalty})
    return sorted(result,key=lambda x:(-x["solved"],x["penalty"],x["user_id"]))

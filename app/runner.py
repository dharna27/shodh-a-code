"""Privileged Docker runner gateway. Development demonstration only; see SECURITY.md."""
import os,subprocess,secrets,json
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel,Field
app=FastAPI()
class Case(BaseModel):
    input:str=Field(max_length=10000)
    expected:str=Field(max_length=10000)
class Execute(BaseModel):
    code:str=Field(max_length=50000)
    cases:list[Case]=Field(min_length=1,max_length=100)

@app.post("/execute")
def execute(body:Execute,x_runner_token:str=Header(default="")):
    if not secrets.compare_digest(x_runner_token,os.getenv("RUNNER_TOKEN","local_runner_token")):
        raise HTTPException(403,"Forbidden")
    # Code and testcase input travel over stdin; no bind mounts or host paths.
    wrapper = "import sys,json,io; p=json.load(sys.stdin); sys.stdin=io.StringIO(p['input']); exec(compile(p['code'],'submission.py','exec'),{'__name__':'__main__'})"
    for case in body.cases:
        name="shodh-"+secrets.token_hex(8)
        cmd=["docker","run","--rm","--name",name,"--network","none","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges","--pids-limit","64","--memory","128m","--cpus","1","--user","65534:65534","--tmpfs","/tmp:rw,noexec,nosuid,size=16m","-i","python:3.12-alpine","python","-I","-B","-c",wrapper]
        try:
            out=subprocess.run(cmd,input=json.dumps({"code":body.code,"input":case.input}),text=True,capture_output=True,timeout=15)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker","rm","-f",name],capture_output=True,timeout=10)
            return {"verdict":"time_limit"}
        except Exception:
            return {"verdict":"judge_failure"}
        if len(out.stdout.encode())>65536 or len(out.stderr.encode())>65536:
            return {"verdict":"output_limit"}
        if out.returncode!=0:
            if "Cannot connect to the Docker daemon" in out.stderr or "Unable to find image" in out.stderr or "docker:" in out.stderr:
                return {"verdict":"judge_failure"}
            return {"verdict":"runtime_error"}
        if out.stdout.strip()!=case.expected.strip():return {"verdict":"wrong_answer"}
    return {"verdict":"accepted"}

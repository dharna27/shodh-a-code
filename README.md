# Shodh a Code — Backend Engineer Intern assessment

**Status: substantial educational implementation, NOT a verified complete submission.** Read `docs/ARCHITECTURE.md` for known gaps before submitting.

## Quick start

Prerequisites: Docker Desktop with Linux containers and WSL2. Run from project root:

```bash
docker compose up --build
```

First-time runner image pull (in a separate terminal):

```bash
docker pull python:3.12-alpine
```

API: http://localhost:8000/docs. Health: http://localhost:8000/health.

Seed identities (`X-User-ID`): 1 Alice (org 1 organizer), 2 Bob (org 1 participant), 3 Olivia (org 2 organizer), 4 Mallory (org 2 participant). Contests 1 and 2. Problems 1, 2, 3.

## Example flow (PowerShell)

```powershell
curl.exe -X POST http://localhost:8000/contests/1/join -H "X-User-ID: 2"
$body = '{"problem_id":1,"language":"python3","code":"a,b=map(int,input().split());print(a+b)"}'
curl.exe -X POST http://localhost:8000/contests/1/submissions -H "X-User-ID: 2" -H "Idempotency-Key: demo-001" -H "Content-Type: application/json" --data-raw $body
curl.exe http://localhost:8000/submissions/1 -H "X-User-ID: 2"
curl.exe http://localhost:8000/contests/1/leaderboard -H "X-User-ID: 2"
```

On Windows PowerShell, JSON escaping through curl.exe can be awkward; use Swagger at `/docs` or `Invoke-RestMethod` if needed.

## Development checks

```bash
docker compose exec api pytest -q
```

Check two independent workers:

```bash
docker compose up -d --scale worker=2
```

These commands are **not** a substitute for race tests and final-database assertions required by the assessment.

## Model

`users`, `organizations`, `memberships`, `contests`, `participations`, `problems`, `problem_versions`, `test_suites`, `test_cases`, `submissions`, `attempts`.

## API

`GET /contests`, `POST /organizations/{org_id}/contests`, `GET /contests/{id}/problems`, `POST /contests/{id}/join`, `POST /contests/{id}/submissions`, `GET /submissions/{id}`, `POST /submissions/{id}/rejudge`, `GET /contests/{id}/leaderboard`.

## Evidence

No real performance or concurrency numbers are included: these must be measured and recorded by the candidate on their machine, with commit, machine resources, configuration, dataset and execution mode. The assessment additionally requires a <=4-page report and optional <=1-page AI assistance disclosure.

## Development caution

The Docker runner uses the host Docker socket and should only be used with controlled local examples on a disposable development host. See `docs/SECURITY.md`.

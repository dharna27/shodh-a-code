# Shodh a Code

A backend for an online coding contest platform, built as part of the Shodh Backend Engineer Intern assessment.

The application allows students to join contests, submit Python solutions, and view their results on a leaderboard. Organizers can create contests and rejudge submissions. Code execution happens asynchronously through a separate worker and Docker-based runner.

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **Database:** PostgreSQL
- **Migrations:** Alembic
- **Code execution:** Docker
- **Infrastructure:** Docker Compose
- **Testing:** Pytest and Python concurrency scripts

## Getting Started

### Prerequisites

- Docker Desktop
- Docker Compose
- WSL2 (for Windows users)
- Python 3 (for running local test scripts)

Clone the repository and navigate to the project directory.

Create a `.env` file in the project root and configure the development authentication secret:

```env
DEV_AUTH_SECRET=replace_with_a_long_random_secret
```

Keep `.env` out of version control.

Start the application:

```bash
docker compose up --build
```

The application automatically runs database migrations and seeds the initial data.

The API documentation is available at:

http://localhost:8000/docs

Health endpoint:

http://localhost:8000/health

The runner uses `python:3.12-alpine` for executing submitted solutions. If the image is not available locally, pull it using:

```bash
docker pull python:3.12-alpine
```

## Development Users

The application comes with seeded users for testing organization and role-based access.

| User ID | Name | Organization | Role |
|---|---|---|---|
| 1 | Alice | 1 | Organizer |
| 2 | Bob | 1 | Participant |
| 3 | Olivia | 2 | Organizer |
| 4 | Mallory | 2 | Participant |

The seeded data also includes two contests and three problems.

For local development, requests use `X-User-ID` and a corresponding `X-Dev-Token`. The token is an HMAC-SHA256 digest generated from the development secret and the user identity.

For example, to generate a token for user 2 in PowerShell:

```powershell
$env:DEV_AUTH_SECRET = "the_same_secret_used_in_your_env_file"

$token = python -c "import os,hmac; print(hmac.new(os.environ['DEV_AUTH_SECRET'].encode(), b'user:2', 'sha256').hexdigest())"
```

The API checks the token before allowing the request. Organization membership and role permissions are checked separately.

This authentication mechanism is intended for local development and assessment testing, not production use.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/contests` | List accessible contests |
| POST | `/organizations/{org_id}/contests` | Create a contest |
| GET | `/contests/{id}/problems` | List contest problems |
| POST | `/contests/{id}/join` | Join a contest |
| POST | `/contests/{id}/submissions` | Submit a solution |
| GET | `/submissions/{id}` | Check submission status |
| POST | `/submissions/{id}/rejudge` | Rejudge a submission |
| GET | `/contests/{id}/leaderboard` | View contest rankings |

Interactive API documentation is available through Swagger UI at `/docs`.

## How Submission Processing Works

When a participant submits code, the API validates the request and stores the submission in PostgreSQL.

A background worker picks up pending attempts and sends them to the runner. The runner executes the submitted Python program inside a restricted Docker container and returns the result.

The worker then updates the attempt with its verdict.

The implementation includes:

- Idempotency keys to avoid duplicate submissions during retries.
- Database row locking to coordinate multiple workers.
- Leases and claim tokens to support recovery after worker failures.
- Separate judging attempts for rejudging submissions.
- Organization and role checks for protected operations.

The runner applies resource limits and disables networking for submitted programs. Its isolation model and limitations are described in `docs/SECURITY.md`.

## Running Tests

Run the available test suite:

```bash
docker compose exec api pytest -q
```

To run two worker instances:

```bash
docker compose up -d --scale worker=2
```

The project also includes scripts for testing concurrent submissions and worker coordination.

From the project root, with the API running and `DEV_AUTH_SECRET` configured in the terminal:

```bash
python test_concurrency.py
python test_multi_worker.py
```

These scripts were used to verify idempotent submission handling and concurrent processing with multiple workers.

## Performance Testing

A local benchmark was run with 20 submissions and a concurrency level of 5.

| Metric | Result |
|---|---|
| Total submissions | 20 |
| Concurrent requests | 5 |
| Submission throughput | 47.82 requests/sec |
| API p50 latency | 102.73 ms |
| API p95 latency | 117.34 ms |
| API p99 latency | 118.15 ms |
| Completed judgements | 20/20 |
| HTTP errors | 0 |
| Submit-to-verdict p50 | 14.66 seconds |
| Submit-to-verdict p95 | 24.30 seconds |

All 20 submissions received an accepted verdict.

The submit-to-verdict measurements include queue waiting, execution time, and polling delay. They should not be interpreted as isolated execution latency.

To run the benchmark again:

```bash
python benchmarks/benchmark_shodh.py
```

The benchmark saves its results in the `evidence/` directory.

A PostgreSQL query-plan inspection was also performed for the worker's attempt lookup. The query completed in approximately 0.108 ms on the tested dataset of 60 attempts.

This was a small local test, so the results are not intended to represent production-scale performance.

## Project Structure

```text
app/
  main.py          # API endpoints
  models.py        # Database models
  worker.py        # Background judging worker
  runner.py        # Docker-based code execution
  seed.py          # Development seed data

alembic/           # Database migrations
benchmarks/        # Performance benchmark
docs/              # Architecture and security notes
evidence/          # Test results, logs and query plans

docker-compose.yml
Dockerfile
test_concurrency.py
test_multi_worker.py
README.md
```

## Known Limitations

This is an assessment implementation rather than a production-ready contest platform.

The development authentication mechanism uses a locally configured secret and is not a replacement for a full production identity system.

The runner gateway requires access to the Docker socket to create execution containers. Submitted programs are executed in separate restricted containers, but the gateway itself remains a privileged component.

The performance results were collected on a small local dataset. Additional load testing and isolation hardening would be necessary before using the system in production.

Further implementation details and known gaps are documented in `docs/ARCHITECTURE.md` and `docs/SECURITY.md`.

## Assessment Notes

The repository includes the application code, database migrations, seed data, Docker configuration, test scripts, and locally collected evidence.

The focus of the implementation is correctness under concurrent submissions, asynchronous judging, recovery from worker failures, and enforcing organization-level access controls.

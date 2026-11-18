# Assessment report (template; replace placeholders with measured evidence)

## Architecture
Describe API, PostgreSQL queue, Docker runner, isolation boundary and limits.

## Transaction and retry boundaries
Document submission+attempt atomic commit, unique idempotency constraint, worker claim and token fencing.

## Rejudge and scoring
Document authoritative current attempt and deterministic ICPC-inspired ranking.

## Security evidence
Record cross-organization and participant/organizer denial tests and hidden-data checks with exact commands.

## Performance evidence
Commit: TODO; machine: TODO; dataset: TODO; mode: TODO; concurrency: TODO; p50/p95/p99: TODO; throughput: TODO; errors: TODO; queue delay: TODO.

## Investigated bottleneck
Before EXPLAIN ANALYZE: TODO; change: TODO; after: TODO; correctness verification: TODO.

## Injected failure and recovery
Failpoint: TODO; logs: TODO; final database state: TODO.

## Known limitations
See `ARCHITECTURE.md`. Disclose any unimplemented assessment requirement.

## AI assistance disclosure (optional separate page)
State which components were AI-assisted and exactly how you tested and understood them.

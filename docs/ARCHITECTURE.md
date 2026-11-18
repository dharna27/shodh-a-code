# Architecture and decisions

- API: FastAPI. `X-User-ID` is an intentionally **trusted development fixture**, not production authentication.
- PostgreSQL: submissions and initial attempts are committed in one transaction. The attempts table itself is the durable work queue, avoiding the commit-to-dispatch gap.
- Worker: `SELECT ... FOR UPDATE SKIP LOCKED` claims attempts. Leases expire after 45 seconds; claim tokens fence stale completions. Up to three attempts at running an attempt are made.
- Rejudge: creates a new attempt and switches `current_attempt_id`; the leaderboard consults only the current completed attempt. Older results remain stored.
- Idempotency: unique `(contest_id,user_id,idem_key)` plus canonical request hash; key conflicts return HTTP 409.
- Ranking: ICPC-inspired, one point per accepted problem; 20 penalty minutes per incorrect completed attempt before first accepted submission, plus elapsed contest minutes. Stable tie by user ID. Infrastructure failures do not count.
- Visibility: participants see their own submission status, organizers may see status in their organization. Hidden tests are not exposed by participant API.

## Known limitations (must resolve before claiming full assessment compliance)

1. Runner service has privileged Docker daemon access; a production solution needs a hardened runner host / restricted daemon and stronger isolation. It must never be publicly exposed.
2. Output size is checked after capture, so it is not an enforced streaming output cap. Implement streaming limits to protect runner memory.
3. Worker lease is fixed and not heartbeated. A slow runner can exceed lease and cause redundant execution, although claim-token fencing prevents duplicate finalization.
4. No complete multi-process concurrency suite, fault injection suite, performance benchmarks or measured before/after query plans yet.
5. Current leaderboard is computed on read (N+1 queries) and is intended as a baseline for benchmarking.
6. Migrations are a single initial schema snapshot; subsequent schema changes should use proper incremental Alembic revisions.
7. Runner has no hardened CPU-time accounting beyond Docker CPU quota and wall timeout; Docker memory limits require host support.
8. Rejudge does not yet update the submission's displayed suite version; attempt suite is authoritative.
9. Current seed is deterministic only on a fresh volume; reset volumes before comparing runs.
10. Real judging and isolation checks have not been verified in this environment.

"""Repeatable mixed API/judge benchmark for the Shodh local development fixture."""
import asyncio
import hashlib
import hmac
import json
import os
import statistics
import time
import uuid
from pathlib import Path

import httpx

BASE = os.getenv('SHODH_BASE_URL', 'http://127.0.0.1:8000')
SECRET = os.environ.get('DEV_AUTH_SECRET')
if not SECRET:
    raise SystemExit('Set DEV_AUTH_SECRET in this PowerShell session first')
COUNT = int(os.getenv('BENCH_COUNT', '20'))
CONCURRENCY = int(os.getenv('BENCH_CONCURRENCY', '5'))
RUN_ID = uuid.uuid4().hex[:10]
HEADERS = {
    'X-User-ID': '2',
    'X-Dev-Token': hmac.new(SECRET.encode(), b'user:2', hashlib.sha256).hexdigest(),
}
PAYLOAD = {'problem_id': 1, 'language': 'python3', 'code': 'a,b=map(int,input().split());print(a+b)'}


def percentiles(xs):
    if not xs:
        return {'p50': None, 'p95': None, 'p99': None}
    xs = sorted(xs)
    def pct(p):
        i = (len(xs)-1)*p
        lo = int(i)
        hi = min(lo+1,len(xs)-1)
        return round(xs[lo] + (xs[hi]-xs[lo])*(i-lo), 2)
    return {'p50':pct(.50), 'p95':pct(.95), 'p99':pct(.99)}


async def main():
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(timeout=30) as client:
        health = await client.get(f'{BASE}/health')
        health.raise_for_status()
        async def submit(i):
            async with sem:
                started = time.perf_counter()
                try:
                    r = await client.post(f'{BASE}/contests/1/submissions', headers={**HEADERS, 'Idempotency-Key':f'bench-{RUN_ID}-{i}'}, json=PAYLOAD)
                    elapsed = (time.perf_counter()-started)*1000
                    body = r.json()
                    return {'status':r.status_code, 'latency_ms':round(elapsed,2), 'submission_id':body.get('submission_id'), 'error':None if r.status_code==202 else str(body)[:250], 'submitted_at':time.perf_counter()}
                except Exception as e:
                    return {'status':None,'latency_ms':round((time.perf_counter()-started)*1000,2),'submission_id':None,'error':str(e),'submitted_at':time.perf_counter()}
        started = time.perf_counter()
        results = await asyncio.gather(*(submit(i) for i in range(COUNT)))
        submit_duration = time.perf_counter()-started
        pending = {r['submission_id']:r for r in results if r['submission_id'] is not None}
        outcomes = {}
        poll_start = time.perf_counter()
        while pending and time.perf_counter()-poll_start < 90:
            async def check(sid, r):
                try:
                    resp = await client.get(f'{BASE}/submissions/{sid}', headers=HEADERS)
                    if resp.status_code != 200:
                        return sid, {'error':f'HTTP {resp.status_code}'}
                    data = resp.json()
                    if data['state']=='completed':
                        return sid, {'verdict':data['verdict'], 'end_to_end_ms':round((time.perf_counter()-r['submitted_at'])*1000,2)}
                except Exception as e:
                    return sid, {'error':str(e)}
                return sid, None
            checked = await asyncio.gather(*(check(sid,r) for sid,r in pending.items()))
            for sid, outcome in checked:
                if outcome is not None:
                    outcomes[sid] = outcome
                    del pending[sid]
            if pending:
                await asyncio.sleep(.25)
        success = [r for r in results if r['status']==202]
        latencies = [r['latency_ms'] for r in results]
        end_to_end = [o['end_to_end_ms'] for o in outcomes.values() if 'end_to_end_ms' in o]
        report = {
            'run_id':RUN_ID, 'requests':COUNT, 'concurrency':CONCURRENCY,
            'submission_duration_seconds':round(submit_duration,3),
            'throughput_requests_per_second':round(COUNT/submit_duration,2),
            'http_202':len(success), 'http_errors':COUNT-len(success),
            'api_latency_ms':percentiles(latencies),
            'completed_judgements':len(end_to_end), 'pending_after_90s':len(pending),
            'submit_to_verdict_ms':percentiles(end_to_end),
            'verdict_counts':{v:sum(o.get('verdict')==v for o in outcomes.values()) for v in sorted({o.get('verdict') for o in outcomes.values() if o.get('verdict')})},
            'note':'submit_to_verdict includes queue wait, execution and polling delay (<=250ms), not isolated queue delay',
            'errors':[r['error'] for r in results if r['error']] + [o['error'] for o in outcomes.values() if 'error' in o],
        }
        Path('evidence').mkdir(exist_ok=True)
        filename = Path('evidence')/f'benchmark_{RUN_ID}.json'
        filename.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
        print('Saved:',filename)


if __name__=='__main__':
    asyncio.run(main())

import os
import hmac


import asyncio
import uuid
import httpx

URL = "http://localhost:8000/contests/1/submissions"

# Unique run identifier avoids reusing keys from previous tests.
RUN_ID = uuid.uuid4().hex[:12]

PAYLOAD = {
    "problem_id": 1,
    "language": "python3",
    "code": "a,b=map(int,input().split());print(a+b)"
}


async def submit(client, number):
    headers = {
        "X-User-ID": "2",
        "X-Dev-Token": hmac.new(os.environ["DEV_AUTH_SECRET"].encode(), b"user:2", "sha256").hexdigest(),
        "Idempotency-Key": f"multi-worker-{RUN_ID}-{number}"
    }

    try:
        response = await client.post(
            URL,
            headers=headers,
            json=PAYLOAD
        )
        result = response.json()

        print(
            f"Request {number}: "
            f"HTTP {response.status_code}, "
            f"Response={result}"
        )

        return response.status_code, result

    except Exception as error:
        print(f"Request {number} failed: {error}")
        return None


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        results = await asyncio.gather(
            *(submit(client, i) for i in range(1, 11))
        )

    successful = [
        r for r in results
        if r is not None and r[0] == 202
    ]

    ids = {
        r[1]["submission_id"]
        for r in successful
    }

    print("\n--- MULTI-WORKER TEST ---")
    print("Requests sent:", len(results))
    print("HTTP 202 responses:", len(successful))
    print("Unique submission IDs:", len(ids))
    print("Submission IDs:", sorted(ids))

    if len(successful) == 10 and len(ids) == 10:
        print("PASS: Ten distinct submissions created")
    else:
        print("FAIL: Check submission responses")


if __name__ == "__main__":
    asyncio.run(main())

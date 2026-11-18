import os
import hmac


import asyncio
import httpx

URL = "http://localhost:8000/contests/1/submissions"

HEADERS = {
    "X-User-ID": "2",
        "X-Dev-Token": hmac.new(os.environ["DEV_AUTH_SECRET"].encode(), b"user:2", "sha256").hexdigest(),
    "Idempotency-Key": "concurrency-test-001"
}

PAYLOAD = {
    "problem_id": 1,
    "language": "python3",
    "code": "a,b=map(int,input().split());print(a+b)"
}


async def submit(client, number):
    try:
        response = await client.post(
            URL,
            headers=HEADERS,
            json=PAYLOAD
        )
        result = response.json()

        print(
            f"Request {number}: "
            f"Status={response.status_code}, "
            f"Response={result}"
        )

        return response.status_code, result

    except Exception as error:
        print(f"Request {number} failed: {error}")
        return None


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [
            submit(client, i)
            for i in range(1, 6)
        ]

        results = await asyncio.gather(*tasks)

    successful = [
        result
        for result in results
        if result is not None and result[0] == 202
    ]

    ids = {
        result[1]["submission_id"]
        for result in successful
    }

    print("\n--- TEST SUMMARY ---")
    print("Total requests:", len(results))
    print("Successful requests:", len(successful))
    print("Unique submission IDs:", ids)

    if len(successful) == 5 and len(ids) == 1:
        print("PASS: All requests reused one submission")
    else:
        print("FAIL: Check responses and database")


if __name__ == "__main__":
    asyncio.run(main())

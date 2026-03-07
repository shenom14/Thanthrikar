import sys
import asyncio
import websockets
import json
import requests


async def run_ws_smoke_test():
    print("Starting session...")
    try:
        res = requests.post("http://127.0.0.1:8000/interviews/start", json={"candidate_id": "rec123"}, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"Failed to start session: {e}", file=sys.stderr)
        return
        
    data = res.json()
    sess_id = data.get("id")
    print(f"Session started: {sess_id}")
    
    uri = f"ws://127.0.0.1:8000/ws/interviewStream/{sess_id}"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected. Sending payload...")
            await ws.send("I increased our user retention by 50% using a custom Python backend.")
            print("Waiting for response...")
            msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
            print("Received:", msg)
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            print("Received:", msg)
    except Exception as e:
        print(f"WS Exception: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Manual smoke test entrypoint; intentionally not collected by pytest.
    asyncio.run(run_ws_smoke_test())

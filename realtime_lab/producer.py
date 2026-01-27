from __future__ import annotations

import argparse
import json
import random
import time

import boto3


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock Kinesis market producer.")
    parser.add_argument("--stream", required=True, help="Kinesis stream name.")
    parser.add_argument("--symbols", default="A,B,C,D", help="Comma-separated symbols.")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between ticks.")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed.")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    prices = {s: 100.0 for s in symbols}

    client = boto3.client("kinesis")

    while True:
        for sym in symbols:
            prices[sym] *= 1.0 + rng.uniform(-0.002, 0.002)
            payload = {
                "symbol": sym,
                "timestamp": time.time(),
                "price": round(prices[sym], 4),
                "source": "mock",
            }
            client.put_record(
                StreamName=args.stream,
                Data=json.dumps(payload).encode("utf-8"),
                PartitionKey=sym,
            )
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

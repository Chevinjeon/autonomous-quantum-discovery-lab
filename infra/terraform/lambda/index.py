import base64
import json
import os
from datetime import datetime

import boto3


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMO_TABLE"])


def handler(event, context):
    for record in event.get("Records", []):
        payload = base64.b64decode(record["kinesis"]["data"]).decode("utf-8")
        tick = json.loads(payload)
        symbol = tick.get("symbol", "UNKNOWN")
        table.put_item(
            Item={
                "symbol": symbol,
                "timestamp": tick.get("timestamp", datetime.utcnow().isoformat()),
                "price": tick.get("price", 0.0),
                "source": tick.get("source", "mock"),
            }
        )
    return {"status": "ok"}

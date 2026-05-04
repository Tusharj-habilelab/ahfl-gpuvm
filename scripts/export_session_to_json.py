#!/usr/bin/env python3
import json
import sys
from datetime import datetime
from pathlib import Path


def to_ms(ts: str):
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return int(datetime.fromisoformat(ts).timestamp() * 1000)
    except Exception:
        return None


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: export_session_to_json.py <input_jsonl> <output_json>")
        return 1

    src = Path(sys.argv[1])
    out = Path(sys.argv[2])

    requests = []
    current_user = None

    with src.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue

            typ = obj.get("type")
            data = obj.get("data", {}) if isinstance(obj.get("data"), dict) else {}

            if typ == "user.message":
                content = data.get("content", "")
                if isinstance(content, str):
                    current_user = content

            elif typ == "assistant.message":
                content = data.get("content", "")
                if not isinstance(content, str) or not content.strip():
                    continue

                requests.append(
                    {
                        "message": {"text": current_user or ""},
                        "response": [content],
                        "timestamp": to_ms(obj.get("timestamp", "")),
                    }
                )
                current_user = None

    payload = {
        "requesterUsername": "User",
        "responderUsername": "GitHub Copilot",
        "requests": requests,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"REQUEST_COUNT={len(requests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

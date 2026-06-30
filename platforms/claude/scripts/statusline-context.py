#!/usr/bin/env python3
import json
import sys


def progress_bar(percent: float, width: int = 12) -> str:
    clamped = max(0.0, min(100.0, percent))
    filled = int(round((clamped / 100.0) * width))
    return "#" * filled + "-" * (width - filled)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print("CTX --.-%")
        return 0

    context = payload.get("context_window") or {}
    used_percentage = context.get("used_percentage")

    if isinstance(used_percentage, (int, float)):
        print(f"CTX {used_percentage:5.1f}% {progress_bar(float(used_percentage))}")
    else:
        print("CTX --.-%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

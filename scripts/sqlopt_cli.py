#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.cli import main


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Final safety net: keep Ctrl+C output compact even if lower layers miss it.
        print({"interrupted": True, "message": "Interrupted by user (Ctrl+C)"})
        raise SystemExit(130)

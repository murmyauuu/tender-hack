from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = DEFAULT_ROOT / "docs" / "integration" / "input_manifest.sha256"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify raw input SHA-256 hashes.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lines = args.manifest.read_text(encoding="utf-8").splitlines()
    passed = 0

    for line in lines:
        expected, relative_path = line.split("  ", 1)
        input_path = args.root / relative_path
        actual = hashlib.sha256(input_path.read_bytes()).hexdigest()
        if actual == expected:
            passed += 1
            print(f"OK     {relative_path}")
        else:
            print(f"FAILED {relative_path}: expected {expected}, got {actual}")

    print(f"{passed}/{len(lines)} OK")
    return 0 if passed == len(lines) else 1


if __name__ == "__main__":
    raise SystemExit(main())

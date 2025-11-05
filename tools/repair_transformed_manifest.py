"""Simple utility to repair transformed manifest JSON files where Annotation keys were
serialized with the internal field-name `from_` instead of the JSON alias `from`.

Usage:
    python tools\repair_transformed_manifest.py <path-to-manifest.json>

The script will create a backup of the original file with `.bak` suffix and write the
fixed content back to the original path.
"""
import sys
from pathlib import Path


def repair_file(path: Path) -> bool:
    if not path.exists():
        print(f"File not found: {path}")
        return False
    txt = path.read_text(encoding="utf-8")
    if '"from_"' not in txt:
        print("No 'from_' keys found — nothing to do.")
        return True
    fixed = txt.replace('"from_"', '"from"')
    bak = path.with_suffix(path.suffix + ".bak")
    path.rename(bak)
    path.write_text(fixed, encoding="utf-8")
    print(f"Repaired manifest. Original backed up to: {bak}")
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python tools\\repair_transformed_manifest.py <manifest.json>")
        sys.exit(2)
    p = Path(sys.argv[1])
    ok = repair_file(p)
    sys.exit(0 if ok else 1)

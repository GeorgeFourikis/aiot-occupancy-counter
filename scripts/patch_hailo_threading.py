from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/patch_hailo_threading.py ~/aiot-workspace/hailo-apps")

    hailo_root = Path(sys.argv[1]).expanduser().resolve()
    matches = list(hailo_root.rglob("camera_utils.py"))

    if not matches:
        raise SystemExit(f"camera_utils.py not found under {hailo_root}")

    path = matches[0]
    text = path.read_text()

    if "import threading" in text:
        print(f"OK: {path} already imports threading")
        return

    backup = path.with_suffix(path.suffix + ".bak_aiot")
    if not backup.exists():
        backup.write_text(text)

    lines = text.splitlines()
    insert_at = 0

    for i, line in enumerate(lines[:80]):
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1

    lines.insert(insert_at, "import threading")
    path.write_text("\n".join(lines) + "\n")

    print(f"Patched missing import threading in: {path}")
    print(f"Backup saved at: {backup}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import sys
from pathlib import Path


IMPORT_BLOCK = '''
# --- AIOT_OCCUPANCY_IMPORT_START ---
import sys as _aiot_sys
from pathlib import Path as _aiot_Path

_aiot_project_src = _aiot_Path.home() / "aiot-workspace" / "aiot-occupancy-counter" / "src"
if str(_aiot_project_src) not in _aiot_sys.path:
    _aiot_sys.path.insert(0, str(_aiot_project_src))

from occupancy.runtime import get_runtime as _aiot_get_occupancy_runtime

_aiot_occupancy_runtime = _aiot_get_occupancy_runtime()
# --- AIOT_OCCUPANCY_IMPORT_END ---
'''


CALL_BLOCK = '''    frame_with_detections = draw_detections(detections, original_frame, labels, tracker=tracker, draw_trail=draw_trail)

    # --- AIOT_OCCUPANCY_CALL_START ---
    try:
        _aiot_occupancy_runtime.update(frame_with_detections, detections, labels)
    except Exception as exc:
        cv2.putText(
            frame_with_detections,
            f"AIoT occupancy error: {exc}",
            (20, 145),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    # --- AIOT_OCCUPANCY_CALL_END ---

    return frame_with_detections'''


ORIGINAL_CALL = '''    frame_with_detections = draw_detections(detections, original_frame, labels, tracker=tracker, draw_trail=draw_trail)
    return frame_with_detections'''


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/patch_hailo_postprocess.py ~/aiot-workspace/hailo-apps")

    hailo_root = Path(sys.argv[1]).expanduser().resolve()
    matches = list(hailo_root.rglob("object_detection_post_process.py"))

    if not matches:
        raise SystemExit(f"object_detection_post_process.py not found under {hailo_root}")

    path = matches[0]
    text = path.read_text()

    if "AIOT_OCCUPANCY_CALL_START" in text:
        print(f"OK: {path} already patched")
        return

    backup = path.with_suffix(path.suffix + ".bak_aiot")
    if not backup.exists():
        backup.write_text(text)

    # Add import block after existing imports. The file imports cv2 near the top, so put our block after cv2 import.
    if "AIOT_OCCUPANCY_IMPORT_START" not in text:
        if "import cv2\n" in text:
            text = text.replace("import cv2\n", "import cv2\n" + IMPORT_BLOCK + "\n", 1)
        else:
            text = IMPORT_BLOCK + "\n" + text

    if ORIGINAL_CALL not in text:
        raise SystemExit(
            "Could not find the expected draw_detections/return block. "
            f"Open this file and patch manually: {path}"
        )

    text = text.replace(ORIGINAL_CALL, CALL_BLOCK, 1)
    path.write_text(text)

    print(f"Patched occupancy hook in: {path}")
    print(f"Backup saved at: {backup}")


if __name__ == "__main__":
    main()

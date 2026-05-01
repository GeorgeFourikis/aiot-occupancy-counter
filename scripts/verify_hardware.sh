#!/usr/bin/env bash
set -e

echo "=== OS ==="
uname -a
echo

echo "=== Debian ==="
cat /etc/os-release | head -5
echo

echo "=== HailoRT ==="
which hailortcli || true
hailortcli fw-control identify || true
echo

echo "=== Raspberry Pi / libcamera cameras ==="
rpicam-hello --list-cameras || true
echo

echo "=== USB / V4L2 cameras ==="
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --list-devices || true
else
  echo "v4l2-ctl not installed. Install with:"
  echo "sudo apt install -y v4l-utils"
fi
echo

echo "=== Video devices ==="
ls -l /dev/video* 2>/dev/null || echo "No /dev/video* devices found"
echo

echo "=== Hailo apps ==="
ls "$HOME/aiot-workspace/hailo-apps" || true
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

echo "=== Cameras ==="
rpicam-hello --list-cameras || true
echo

echo "=== Hailo apps ==="
ls "$HOME/aiot-workspace/hailo-apps" || true

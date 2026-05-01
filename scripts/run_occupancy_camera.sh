#!/usr/bin/env bash
set -eo pipefail

CAMERA_INPUT="${1:-rpi}"
CAMERA_ID="${2:-rpi5_imx500_01}"

export AIOT_CAMERA_ID="$CAMERA_ID"

echo "Starting AIoT occupancy counter"
echo "Camera input: $CAMERA_INPUT"
echo "Camera ID:    $AIOT_CAMERA_ID"

cd "$HOME/aiot-workspace/hailo-apps"

# Hailo's setup_env.sh may reference shell variables that are unset.
# So we intentionally avoid "set -u" before sourcing it.
source setup_env.sh

cd "$HOME/aiot-workspace/hailo-apps/hailo_apps/python/standalone_apps/object_detection"

./object_detection.py -n yolov8n -i "$CAMERA_INPUT" --show-fps
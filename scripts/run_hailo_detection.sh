#!/usr/bin/env bash
set -eo pipefail

cd "$HOME/aiot-workspace/hailo-apps"
source setup_env.sh

cd "$HOME/aiot-workspace/hailo-apps/hailo_apps/python/standalone_apps/object_detection"

./object_detection.py -n yolov8n -i rpi --show-fps

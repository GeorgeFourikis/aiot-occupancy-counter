#!/usr/bin/env bash
set -eo pipefail

cd "$HOME/aiot-workspace/hailo-apps"

# Hailo's setup_env.sh may reference shell variables that are unset.
# So we intentionally avoid "set -u" before sourcing it.
source setup_env.sh

cd "$HOME/aiot-workspace/hailo-apps/hailo_apps/python/standalone_apps/object_detection"

./object_detection.py -n yolov8n -i rpi --show-fps

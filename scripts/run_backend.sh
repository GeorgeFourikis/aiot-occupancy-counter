#!/usr/bin/env bash
set -eo pipefail

cd "$HOME/aiot-workspace/hailo-apps"
source setup_env.sh

cd "$HOME/aiot-workspace/aiot-occupancy-counter"

export PYTHONPATH="$HOME/aiot-workspace/aiot-occupancy-counter/src:$PYTHONPATH"

uvicorn occupancy.backend:app --host 0.0.0.0 --port 8000 --reload

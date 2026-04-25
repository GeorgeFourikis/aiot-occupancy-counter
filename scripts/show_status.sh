#!/usr/bin/env bash
set -e

DB="$HOME/aiot-workspace/aiot-occupancy-counter/data/occupancy.db"

if [ ! -f "$DB" ]; then
  echo "No database found yet: $DB"
  exit 1
fi

sqlite3 "$DB" <<'SQL'
.headers on
.mode column

SELECT *
FROM occupancy_events
ORDER BY id DESC
LIMIT 20;
SQL

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

.print '=== Latest events ==='
SELECT
  id,
  timestamp_utc,
  camera_id,
  event_type,
  raw_people_count,
  smoothed_people_count,
  confirmed_people_count,
  occupancy_state
FROM occupancy_events
ORDER BY id DESC
LIMIT 20;

.print ''
.print '=== Latest state per camera ==='
SELECT
  e.camera_id,
  e.timestamp_utc,
  e.confirmed_people_count,
  e.occupancy_state
FROM occupancy_events e
JOIN (
  SELECT camera_id, MAX(id) AS latest_id
  FROM occupancy_events
  GROUP BY camera_id
) latest
ON e.id = latest.latest_id
ORDER BY e.camera_id;
SQL
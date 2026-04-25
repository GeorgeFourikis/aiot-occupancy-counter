from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse


PROJECT_ROOT = Path.home() / "aiot-workspace" / "aiot-occupancy-counter"
DB_PATH = PROJECT_ROOT / "data" / "occupancy.db"

app = FastAPI(
    title="AIoT Occupancy Counter API",
    version="0.1.0",
)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database does not exist yet: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None

    return dict(row)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "database_exists": DB_PATH.exists(),
        "database_path": str(DB_PATH),
    }


@app.get("/current")
def current() -> dict[str, Any]:
    try:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    timestamp_utc,
                    site_id,
                    camera_id,
                    event_type,
                    raw_people_count,
                    smoothed_people_count,
                    confirmed_people_count,
                    occupancy_state
                FROM occupancy_events
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
    except FileNotFoundError as exc:
        return {
            "status": "no_data",
            "message": str(exc),
        }

    latest = _row_to_dict(row)

    if latest is None:
        return {
            "status": "no_data",
            "message": "No occupancy events found yet.",
        }

    return {
        "status": "ok",
        "current": latest,
    }


@app.get("/events")
def events(limit: int = Query(default=20, ge=1, le=500)) -> dict[str, Any]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    timestamp_utc,
                    site_id,
                    camera_id,
                    event_type,
                    raw_people_count,
                    smoothed_people_count,
                    confirmed_people_count,
                    occupancy_state
                FROM occupancy_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    except FileNotFoundError as exc:
        return {
            "status": "no_data",
            "message": str(exc),
            "events": [],
        }

    return {
        "status": "ok",
        "events": [_row_to_dict(row) for row in rows],
    }


@app.get("/summary")
def summary() -> dict[str, Any]:
    try:
        with _connect() as conn:
            total_events = conn.execute(
                "SELECT COUNT(*) FROM occupancy_events"
            ).fetchone()[0]

            latest_row = conn.execute(
                """
                SELECT *
                FROM occupancy_events
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

            max_count = conn.execute(
                """
                SELECT MAX(confirmed_people_count)
                FROM occupancy_events
                """
            ).fetchone()[0]

            changes = conn.execute(
                """
                SELECT COUNT(*)
                FROM occupancy_events
                WHERE event_type = 'occupancy_change'
                """
            ).fetchone()[0]
    except FileNotFoundError as exc:
        return {
            "status": "no_data",
            "message": str(exc),
        }

    return {
        "status": "ok",
        "total_events": total_events,
        "occupancy_changes": changes,
        "max_confirmed_people_count": max_count,
        "latest": _row_to_dict(latest_row),
    }


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return """
<!doctype html>
<html>
<head>
  <title>AIoT Occupancy Counter</title>
  <meta charset="utf-8">
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 40px;
      background: #111827;
      color: #f9fafb;
    }
    .card {
      background: #1f2937;
      padding: 24px;
      border-radius: 14px;
      max-width: 760px;
      margin-bottom: 20px;
    }
    .count {
      font-size: 64px;
      font-weight: bold;
    }
    .state {
      font-size: 28px;
      margin-top: 8px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
    }
    th, td {
      padding: 8px;
      border-bottom: 1px solid #374151;
      text-align: left;
    }
    .muted {
      color: #9ca3af;
    }
  </style>
</head>
<body>
  <h1>AIoT Occupancy Counter</h1>

  <div class="card">
    <div class="muted">Current confirmed people count</div>
    <div id="count" class="count">-</div>
    <div id="state" class="state">Loading...</div>
    <p class="muted" id="timestamp"></p>
  </div>

  <div class="card">
    <h2>Recent events</h2>
    <table>
      <thead>
        <tr>
          <th>Time</th>
          <th>Event</th>
          <th>Raw</th>
          <th>Smoothed</th>
          <th>Confirmed</th>
          <th>State</th>
        </tr>
      </thead>
      <tbody id="events"></tbody>
    </table>
  </div>

<script>
async function refresh() {
  const currentResponse = await fetch('/current');
  const currentData = await currentResponse.json();

  if (currentData.status === 'ok') {
    const c = currentData.current;
    document.getElementById('count').textContent = c.confirmed_people_count;
    document.getElementById('state').textContent = c.occupancy_state;
    document.getElementById('timestamp').textContent = c.timestamp_utc;
  } else {
    document.getElementById('count').textContent = '-';
    document.getElementById('state').textContent = 'No data yet';
    document.getElementById('timestamp').textContent = '';
  }

  const eventsResponse = await fetch('/events?limit=10');
  const eventsData = await eventsResponse.json();

  const tbody = document.getElementById('events');
  tbody.innerHTML = '';

  for (const event of eventsData.events || []) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${event.timestamp_utc}</td>
      <td>${event.event_type}</td>
      <td>${event.raw_people_count}</td>
      <td>${event.smoothed_people_count}</td>
      <td>${event.confirmed_people_count}</td>
      <td>${event.occupancy_state}</td>
    `;
    tbody.appendChild(row);
  }
}

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""

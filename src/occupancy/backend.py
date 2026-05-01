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
    version="0.2.0",
)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database does not exist yet: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH, timeout=10.0)
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
                SELECT *
                FROM occupancy_events
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
    except FileNotFoundError as exc:
        return {"status": "no_data", "message": str(exc)}

    latest = _row_to_dict(row)

    if latest is None:
        return {"status": "no_data", "message": "No occupancy events found yet."}

    return {"status": "ok", "current": latest}


@app.get("/current/{camera_id}")
def current_by_camera(camera_id: str) -> dict[str, Any]:
    try:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM occupancy_events
                WHERE camera_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (camera_id,),
            ).fetchone()
    except FileNotFoundError as exc:
        return {"status": "no_data", "message": str(exc)}

    latest = _row_to_dict(row)

    if latest is None:
        return {
            "status": "no_data",
            "message": f"No occupancy events found for camera_id={camera_id}.",
        }

    return {"status": "ok", "current": latest}


@app.get("/cameras")
def cameras() -> dict[str, Any]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT e.*
                FROM occupancy_events e
                JOIN (
                    SELECT camera_id, MAX(id) AS latest_id
                    FROM occupancy_events
                    GROUP BY camera_id
                ) latest
                ON e.id = latest.latest_id
                ORDER BY e.camera_id
                """
            ).fetchall()
    except FileNotFoundError as exc:
        return {"status": "no_data", "message": str(exc), "cameras": []}

    camera_states = [_row_to_dict(row) for row in rows]

    total_visible_people = sum(
        int(row["confirmed_people_count"])
        for row in camera_states
        if row is not None
    )

    return {
        "status": "ok",
        "total_visible_people": total_visible_people,
        "cameras": camera_states,
    }


@app.get("/events")
def events(limit: int = Query(default=20, ge=1, le=500)) -> dict[str, Any]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM occupancy_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    except FileNotFoundError as exc:
        return {"status": "no_data", "message": str(exc), "events": []}

    return {"status": "ok", "events": [_row_to_dict(row) for row in rows]}


@app.get("/summary")
def summary() -> dict[str, Any]:
    try:
        with _connect() as conn:
            total_events = conn.execute("SELECT COUNT(*) FROM occupancy_events").fetchone()[0]

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

            camera_count = conn.execute(
                """
                SELECT COUNT(DISTINCT camera_id)
                FROM occupancy_events
                """
            ).fetchone()[0]
    except FileNotFoundError as exc:
        return {"status": "no_data", "message": str(exc)}

    return {
        "status": "ok",
        "total_events": total_events,
        "occupancy_changes": changes,
        "camera_count": camera_count,
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
      max-width: 980px;
      margin-bottom: 20px;
    }
    .big {
      font-size: 52px;
      font-weight: bold;
    }
    .camera-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      max-width: 980px;
    }
    .camera-card {
      background: #1f2937;
      padding: 20px;
      border-radius: 14px;
    }
    .muted {
      color: #9ca3af;
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
  </style>
</head>
<body>
  <h1>AIoT Occupancy Counter</h1>

  <div class="card">
    <div class="muted">Total visible people across latest camera states</div>
    <div id="total" class="big">-</div>
    <p class="muted">
      Note: total is meaningful only when camera views do not overlap.
    </p>
  </div>

  <h2>Camera states</h2>
  <div id="cameras" class="camera-grid"></div>

  <div class="card">
    <h2>Recent events</h2>
    <table>
      <thead>
        <tr>
          <th>Time</th>
          <th>Camera</th>
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
  const camerasResponse = await fetch('/cameras');
  const camerasData = await camerasResponse.json();

  document.getElementById('total').textContent =
    camerasData.status === 'ok' ? camerasData.total_visible_people : '-';

  const camerasDiv = document.getElementById('cameras');
  camerasDiv.innerHTML = '';

  for (const cam of camerasData.cameras || []) {
    const div = document.createElement('div');
    div.className = 'camera-card';
    div.innerHTML = `
      <div class="muted">${cam.camera_id}</div>
      <div class="big">${cam.confirmed_people_count}</div>
      <div>${cam.occupancy_state}</div>
      <p class="muted">${cam.timestamp_utc}</p>
    `;
    camerasDiv.appendChild(div);
  }

  const eventsResponse = await fetch('/events?limit=15');
  const eventsData = await eventsResponse.json();

  const tbody = document.getElementById('events');
  tbody.innerHTML = '';

  for (const event of eventsData.events || []) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${event.timestamp_utc}</td>
      <td>${event.camera_id}</td>
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
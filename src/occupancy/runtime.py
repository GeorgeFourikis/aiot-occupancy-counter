from __future__ import annotations

import csv
import json
import sqlite3
import statistics
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2


PROJECT_ROOT = Path.home() / "aiot-workspace" / "aiot-occupancy-counter"
CONFIG_PATH = PROJECT_ROOT / "config" / "app.json"


@dataclass(frozen=True)
class OccupancyConfig:
    site_id: str
    camera_id: str
    person_class_id: int
    person_class_name: str
    confidence_threshold: float
    smoothing_window: int
    occupied_confirmation_seconds: float
    empty_confirmation_seconds: float
    count_change_confirmation_seconds: float
    heartbeat_interval_seconds: float
    csv_log_path: Path
    sqlite_path: Path
    draw_overlay: bool

    @staticmethod
    def load() -> "OccupancyConfig":
        data = json.loads(CONFIG_PATH.read_text())

        return OccupancyConfig(
            site_id=data.get("site_id", "default_site"),
            camera_id=data.get("camera_id", "camera_01"),
            person_class_id=int(data.get("person_class_id", 0)),
            person_class_name=data.get("person_class_name", "person"),
            confidence_threshold=float(data.get("confidence_threshold", 0.40)),
            smoothing_window=int(data.get("smoothing_window", 41)),
            occupied_confirmation_seconds=float(data.get("occupied_confirmation_seconds", 1.5)),
            empty_confirmation_seconds=float(data.get("empty_confirmation_seconds", 8.0)),
            count_change_confirmation_seconds=float(data.get("count_change_confirmation_seconds", 5.0)),
            heartbeat_interval_seconds=float(data.get("heartbeat_interval_seconds", 20.0)),
            csv_log_path=PROJECT_ROOT / data.get("csv_log_path", "data/logs/occupancy_events.csv"),
            sqlite_path=PROJECT_ROOT / data.get("sqlite_path", "data/occupancy.db"),
            draw_overlay=bool(data.get("draw_overlay", True)),
        )


class OccupancyRuntime:
    def __init__(self, config: OccupancyConfig) -> None:
        self.config = config

        self.count_window: deque[int] = deque(maxlen=max(1, config.smoothing_window))

        self.confirmed_count: int | None = None
        self.candidate_count: int | None = None
        self.candidate_since_monotonic: float | None = None

        self.last_log_time_monotonic: float = 0.0

        self.config.csv_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_sqlite()
        self._init_csv()

    def update(self, frame: Any, detections: dict[str, Any], labels: list[str]) -> None:
        raw_count = self._count_people(detections, labels)
        self.count_window.append(raw_count)

        smoothed_count = self._smoothed_count()
        confirmed_count = self._update_confirmed_count(raw_count, smoothed_count)

        state = "occupied" if confirmed_count > 0 else "empty"

        now = time.monotonic()
        heartbeat_due = now - self.last_log_time_monotonic >= self.config.heartbeat_interval_seconds

        if heartbeat_due:
            self._log_event(
                event_type="occupancy_heartbeat",
                raw_count=raw_count,
                smoothed_count=smoothed_count,
                confirmed_count=confirmed_count,
                state=state,
            )
            self.last_log_time_monotonic = now

        if self.config.draw_overlay and frame is not None:
            self._draw_overlay(
                frame=frame,
                raw_count=raw_count,
                smoothed_count=smoothed_count,
                confirmed_count=confirmed_count,
                state=state,
            )

    def _update_confirmed_count(self, raw_count: int, smoothed_count: int) -> int:
        now = time.monotonic()

        if self.confirmed_count is None:
            self.confirmed_count = smoothed_count
            self._log_event(
                event_type="occupancy_initial",
                raw_count=raw_count,
                smoothed_count=smoothed_count,
                confirmed_count=smoothed_count,
                state="occupied" if smoothed_count > 0 else "empty",
            )
            self.last_log_time_monotonic = now
            return self.confirmed_count

        if smoothed_count == self.confirmed_count:
            self.candidate_count = None
            self.candidate_since_monotonic = None
            return self.confirmed_count

        if self.candidate_count != smoothed_count:
            self.candidate_count = smoothed_count
            self.candidate_since_monotonic = now
            return self.confirmed_count

        assert self.candidate_since_monotonic is not None

        candidate_age = now - self.candidate_since_monotonic
        required_age = self._required_confirmation_seconds(
            current_count=self.confirmed_count,
            candidate_count=smoothed_count,
        )

        if candidate_age >= required_age:
            old_count = self.confirmed_count
            self.confirmed_count = smoothed_count
            self.candidate_count = None
            self.candidate_since_monotonic = None

            self._log_event(
                event_type="occupancy_change",
                raw_count=raw_count,
                smoothed_count=smoothed_count,
                confirmed_count=smoothed_count,
                state="occupied" if smoothed_count > 0 else "empty",
            )
            self.last_log_time_monotonic = now

            print(f"STATE CHANGE | {old_count} -> {self.confirmed_count}", flush=True)

        return self.confirmed_count

    def _required_confirmation_seconds(self, current_count: int, candidate_count: int) -> float:
        if current_count == 0 and candidate_count > 0:
            return self.config.occupied_confirmation_seconds

        if current_count > 0 and candidate_count == 0:
            return self.config.empty_confirmation_seconds

        return self.config.count_change_confirmation_seconds

    def _count_people(self, detections: dict[str, Any], labels: list[str]) -> int:
        classes = detections.get("detection_classes", [])
        scores = detections.get("detection_scores", [])

        count = 0

        for class_id, score in zip(classes, scores):
            class_id_int = int(class_id)
            score_float = float(score)

            label = labels[class_id_int] if 0 <= class_id_int < len(labels) else ""

            is_person_by_id = class_id_int == self.config.person_class_id
            is_person_by_name = label.lower() == self.config.person_class_name.lower()

            if (is_person_by_id or is_person_by_name) and score_float >= self.config.confidence_threshold:
                count += 1

        return count

    def _smoothed_count(self) -> int:
        if not self.count_window:
            return 0

        return int(round(statistics.median(self.count_window)))

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.config.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS occupancy_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_utc TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    raw_people_count INTEGER NOT NULL,
                    smoothed_people_count INTEGER NOT NULL,
                    confirmed_people_count INTEGER NOT NULL,
                    occupancy_state TEXT NOT NULL
                )
                """
            )

    def _init_csv(self) -> None:
        if self.config.csv_log_path.exists():
            return

        with self.config.csv_log_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp_utc",
                    "site_id",
                    "camera_id",
                    "event_type",
                    "raw_people_count",
                    "smoothed_people_count",
                    "confirmed_people_count",
                    "occupancy_state",
                ]
            )

    def _log_event(
        self,
        event_type: str,
        raw_count: int,
        smoothed_count: int,
        confirmed_count: int,
        state: str,
    ) -> None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

        row = [
            timestamp,
            self.config.site_id,
            self.config.camera_id,
            event_type,
            raw_count,
            smoothed_count,
            confirmed_count,
            state,
        ]

        with self.config.csv_log_path.open("a", newline="") as f:
            csv.writer(f).writerow(row)

        with sqlite3.connect(self.config.sqlite_path) as conn:
            conn.execute(
                """
                INSERT INTO occupancy_events (
                    timestamp_utc,
                    site_id,
                    camera_id,
                    event_type,
                    raw_people_count,
                    smoothed_people_count,
                    confirmed_people_count,
                    occupancy_state
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )

        print(
            f"OCCUPANCY | {timestamp} | event={event_type} | "
            f"raw={raw_count} | smoothed={smoothed_count} | "
            f"confirmed={confirmed_count} | state={state}",
            flush=True,
        )

    def _draw_overlay(
        self,
        frame: Any,
        raw_count: int,
        smoothed_count: int,
        confirmed_count: int,
        state: str,
    ) -> None:
        candidate_text = "none"

        if self.candidate_count is not None and self.candidate_since_monotonic is not None:
            age = time.monotonic() - self.candidate_since_monotonic
            required = self._required_confirmation_seconds(
                current_count=confirmed_count,
                candidate_count=self.candidate_count,
            )
            candidate_text = f"{self.candidate_count} for {age:.1f}/{required:.1f}s"

        cv2.rectangle(frame, (10, 10), (560, 155), (0, 0, 0), -1)

        cv2.putText(
            frame,
            "AIoT Occupancy Counter",
            (20, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            f"Confirmed people: {confirmed_count}",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            f"Raw: {raw_count} | Smoothed: {smoothed_count}",
            (20, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            f"State: {state} | Candidate: {candidate_text}",
            (20, 130),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )


_RUNTIME: OccupancyRuntime | None = None


def get_runtime() -> OccupancyRuntime:
    global _RUNTIME

    if _RUNTIME is None:
        _RUNTIME = OccupancyRuntime(OccupancyConfig.load())

    return _RUNTIME

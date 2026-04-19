from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AIHistoryStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._history_path = self._root / "ai_history.json"
        self._audit_path = self._root / "ai_audit.json"
        self._lock = threading.Lock()

    def _read(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default.copy()
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return default.copy()

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(path)

    def get_known_clients(self) -> set[str]:
        with self._lock:
            data = self._read(self._history_path, {"records": [], "known_clients": []})
            return {item.lower() for item in data.get("known_clients", []) if isinstance(item, str)}

    def remember_clients(self, macs: set[str]) -> None:
        with self._lock:
            data = self._read(self._history_path, {"records": [], "known_clients": []})
            known = {item.lower() for item in data.get("known_clients", []) if isinstance(item, str)}
            known.update(mac.lower() for mac in macs)
            data["known_clients"] = sorted(known)
            self._write(self._history_path, data)

    def append_history(self, category: str, payload: dict[str, Any], max_records: int = 200) -> None:
        with self._lock:
            data = self._read(self._history_path, {"records": [], "known_clients": []})
            records = list(data.get("records", []))
            records.append(
                {
                    "category": category,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": payload,
                }
            )
            data["records"] = records[-max_records:]
            self._write(self._history_path, data)

    def append_audit(self, payload: dict[str, Any], max_records: int = 500) -> None:
        with self._lock:
            data = self._read(self._audit_path, {"records": []})
            records = list(data.get("records", []))
            records.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **payload,
                }
            )
            data["records"] = records[-max_records:]
            self._write(self._audit_path, data)

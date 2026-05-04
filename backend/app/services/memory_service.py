from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.memory_policy import MemoryScope


class MemoryServiceError(RuntimeError):
    """Raised when MemPalace operations fail in a controlled way."""


@dataclass(frozen=True)
class MemoryHit:
    class_name: str
    fact: str
    confidence_score: float
    project_id: str | None = None
    timestamp: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySearchResult:
    hits: tuple[MemoryHit, ...]
    status: str
    latency_ms: int


@dataclass(frozen=True)
class MemoryMineResult:
    status: str
    mined_count: int


class MemoryService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._command = "mempalace"

    def search(
        self,
        query: str,
        scope: MemoryScope,
        classes: list[str],
        k: int,
    ) -> MemorySearchResult:
        if not query.strip():
            return MemorySearchResult(hits=(), status="empty_query", latency_ms=0)
        if k <= 0:
            raise ValueError("k must be positive")

        started_at = time.perf_counter()
        command = self._build_search_command(
            query=query,
            scope=scope,
            classes=classes,
            k=k,
        )
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._settings.memory_command_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise MemoryServiceError("memory search timed out") from exc
        except OSError as exc:
            raise MemoryServiceError("memory service unavailable") from exc

        if completed.returncode != 0:
            raise MemoryServiceError("memory search failed")

        hits = self._parse_hits(
            completed.stdout, fallback_class=classes[0] if classes else "unknown"
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return MemorySearchResult(hits=hits, status="ok", latency_ms=latency_ms)

    def mine(
        self,
        payload: dict[str, Any],
        scope: MemoryScope,
        class_name: str,
    ) -> MemoryMineResult:
        import tempfile
        import shutil

        # MemPalace expects a directory structure for rooms (classes)
        # e.g. <dir>/<class_name>/payload.json
        temp_dir = tempfile.mkdtemp(prefix="memp_mine_")
        try:
            target_dir = Path(temp_dir) / class_name
            target_dir.mkdir(parents=True)
            
            # Write payload to a file. We embed the project ID so it's queryable if needed.
            file_payload = {"project_id": scope.project_id, **payload}
            import uuid
            file_path = target_dir / f"{uuid.uuid4().hex[:8]}.txt"
            
            # Convert JSON payload to a readable text format for better memory extraction
            content = f"Event: {payload.get('event_type')}\n"
            content += f"Title: {payload.get('title')}\n"
            if payload.get("description"):
                content += f"Content: {payload.get('description')}\n"
            file_path.write_text(content)

            # Initialize the temp directory so MemPalace can discover the rooms (classes)
            subprocess.run(
                [self._command, "init", temp_dir, "--yes"],
                check=True,
                capture_output=True,
                timeout=5,
            )

            command = [
                self._command,
                "--palace",
                self._palace_path(scope),
                "mine",
                temp_dir,
                "--wing",
                scope.workspace_id,
                "--agent",
                "system",
            ]

            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self._settings.memory_command_timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise MemoryServiceError("memory mine timed out") from exc
            except OSError as exc:
                raise MemoryServiceError("memory service unavailable") from exc

            if completed.returncode != 0:
                raise MemoryServiceError(f"memory mine failed: {completed.stderr}")

            # Note: standard mempalace terminal output does not return a JSON with mined_count
            # so we just say 1 since we passed 1 file.
            mined_count = 1
            return MemoryMineResult(status="ok", mined_count=mined_count)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def status(self, scope: MemoryScope) -> dict[str, str]:
        return {
            "status": "enabled" if self._settings.memory_enabled else "disabled",
            "palace": self._palace_path(scope),
        }

    def _palace_path(self, scope: MemoryScope) -> str:
        root = Path(self._settings.memory_palace_root)
        return (root / f"org_{scope.org_id}").as_posix()

    def _build_search_command(
        self,
        *,
        query: str,
        scope: MemoryScope,
        classes: list[str],
        k: int,
    ) -> list[str]:
        command = [
            self._command,
            "--palace",
            self._palace_path(scope),
            "search",
            query,
            "--results",
            str(k),
            "--wing",
            scope.workspace_id,
        ]
        # Standard mempalace search allows exactly ONE --room argument (matches our class_name)
        if classes:
            command.extend(["--room", classes[0]])
        return command

    def _parse_hits(self, stdout: str, fallback_class: str) -> tuple[MemoryHit, ...]:
        raw = stdout.strip()
        if not raw:
            return ()

        parsed: list[MemoryHit] = []
        try:
            payload = json.loads(raw)
            hit_items: list[dict[str, Any]]
            if isinstance(payload, dict):
                maybe_hits = payload.get("hits", [])
                hit_items = maybe_hits if isinstance(maybe_hits, list) else []
            elif isinstance(payload, list):
                hit_items = payload
            else:
                hit_items = []
            for item in hit_items:
                if isinstance(item, dict):
                    hit = self._normalize_hit(item, fallback_class=fallback_class)
                    if hit:
                        parsed.append(hit)
        except json.JSONDecodeError:
            for line in raw.splitlines():
                fact = line.strip()
                if fact:
                    parsed.append(
                        MemoryHit(
                            class_name=fallback_class,
                            fact=fact,
                            confidence_score=0.0,
                        )
                    )
        return tuple(parsed)

    def _normalize_hit(
        self,
        item: dict[str, Any],
        *,
        fallback_class: str,
    ) -> MemoryHit | None:
        fact = item.get("fact") or item.get("text") or item.get("content")
        if not isinstance(fact, str):
            return None
        class_name = item.get("class") or item.get("class_name") or fallback_class
        if not isinstance(class_name, str):
            class_name = fallback_class

        confidence_raw = item.get("confidence")
        if confidence_raw is None:
            confidence_raw = item.get("confidence_score", 0.0)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        project_id = item.get("project_id")
        if not isinstance(project_id, str):
            project_id = None
        timestamp = item.get("ts") or item.get("timestamp")
        if not isinstance(timestamp, str):
            timestamp = None

        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        return MemoryHit(
            class_name=class_name,
            fact=fact.strip(),
            confidence_score=confidence,
            project_id=project_id,
            timestamp=timestamp,
            metadata=metadata,
        )

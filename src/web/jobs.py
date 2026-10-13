"""Фоновые задачи и SSE-поток прогресса.

Долгие операции (скачивание, batch, большие сканы) выполняются в отдельном
потоке. ``Job`` хранит события (прогресс) и итоговый результат/ошибку;
``GET /api/jobs/{id}/events`` стримит их в браузер через Server-Sent Events.
"""
from __future__ import annotations

import json
import time
import uuid
from threading import Lock, Thread
from typing import Any, Callable

from fastapi.responses import StreamingResponse

RenderableMessage = str | dict[str, Any]


class JobFailure(Exception):
    """Known application-owned terminal failure with a renderable message."""

    def __init__(self, error: RenderableMessage) -> None:
        super().__init__(error if isinstance(error, str) else str(error.get("message", "Error")))
        self.error = error

_STATUS_QUEUED = "queued"
_STATUS_RUNNING = "running"
_STATUS_DONE = "done"
_STATUS_ERROR = "error"


class Job:
    """Одна фоновая задача с прогрессом и результатом."""

    def __init__(self, job_id: str, name: RenderableMessage) -> None:
        self.id = job_id
        self.name = name
        self.status = _STATUS_QUEUED
        self.events: list[dict[str, Any]] = []
        self.result: Any = None
        self.error: RenderableMessage | None = None
        self.created_at = time.time()
        self._lock = Lock()

    def to_dict(self) -> dict[str, Any]:
        """Короткое представление для списка/статуса (для дока загрузок)."""
        with self._lock:
            progress = [e for e in self.events if e.get("type") == "progress"][-1:]
            return {
                "id": self.id,
                "name": self.name,
                "status": self.status,
                "result": self.result,
                "error": self.error,
                "progress": progress,
                "created_at": self.created_at,
            }

    # --- API для рабочей функции --------------------------------------

    def push(self, msg: RenderableMessage, percent: float | None = None, **extra: Any) -> None:
        """Добавить событие прогресса (потокобезопасно)."""
        # ``msg`` remains in the wire event while old clients are migrated.
        legacy_msg = msg if isinstance(msg, str) else str(msg.get("message", ""))
        event: dict[str, Any] = {"type": "progress", "message": msg, "msg": legacy_msg}
        if percent is not None:
            event["percent"] = percent
        event.update(extra)
        with self._lock:
            self.events.append(event)

    def done(self, result: Any = None) -> None:
        """Отметить успешное завершение."""
        with self._lock:
            self.status = _STATUS_DONE
            self.result = result
            self.events.append({"type": "done"})

    def fail(self, error: RenderableMessage) -> None:
        """Отметить провал."""
        with self._lock:
            self.status = _STATUS_ERROR
            self.error = error
            self.events.append({"type": "error", "error": error})

    # --- SSE -----------------------------------------------------------

    def stream(self) -> StreamingResponse:
        """StreamingResponse: события задачи по мере появления."""

        def gen():
            last = 0
            while True:
                with self._lock:
                    cur = list(self.events[last:])
                    last = len(self.events)
                    status = self.status
                for ev in cur:
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if status in (_STATUS_DONE, _STATUS_ERROR):
                    yield f"data: {json.dumps({'type': 'end'})}\n\n"
                    return
                time.sleep(0.5)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})


class JobManager:
    """Реестр задач: запуск в потоке, получение по id."""

    # Сколько задач храним для дока загрузок (кольцевой буфер).
    MAX_KEEP = 50

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._lock = Lock()

    def submit(self, name: RenderableMessage, fn: Callable[[Job], Any]) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id, name)
        with self._lock:
            self._jobs[job_id] = job
            self._order.append(job_id)
            # Чистим старые завершённые, активные не трогаем.
            while len(self._order) > self.MAX_KEEP:
                oldest_id = self._order[0]
                oldest = self._jobs.get(oldest_id)
                if oldest is None or oldest.status in (_STATUS_DONE, _STATUS_ERROR):
                    self._order.pop(0)
                    self._jobs.pop(oldest_id, None)
                else:
                    break

        def run() -> None:
            try:
                result = fn(job)
                job.done(result)
            except JobFailure as e:
                job.fail(e.error)
            except Exception as e:  # noqa: BLE001
                job.fail(str(e))

        Thread(target=run, name=f"job-{job_id}", daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 30) -> list[dict[str, Any]]:
        """Последние задачи (новые сверху) для дока загрузок."""
        with self._lock:
            ids = list(self._order[-limit:])
        out = []
        for job_id in reversed(ids):
            job = self.get(job_id)
            if job is not None:
                out.append(job.to_dict())
        return out


jobs = JobManager()

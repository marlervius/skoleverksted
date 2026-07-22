from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

from .models import Job, QualityPassportRequest, utc_now
from .quality import build_quality_passport
from .store import get_platform_store


_STATUS_MAP = {
    "pending": "queued",
    "queued": "queued",
    "planning": "planning",
    "running": "generating",
    "generating": "generating",
    "verifying": "verifying",
    "rendering": "rendering",
    "success": "completed",
    "completed": "completed",
    "completed_with_warnings": "needs_review",
    "needs_review": "needs_review",
    "failed": "failed",
    "error": "failed",
    "cancelled": "cancelled",
}


def _module_for_path(path: str) -> str | None:
    for module in ("fag", "norsk", "matematikk"):
        if path.startswith(f"/api/{module}/"):
            return module
    return None


def _job_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("job_id", "generation_id", "jobId", "generationId"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    nested = payload.get("result")
    return _job_id(nested) if isinstance(nested, dict) else None


def _job_id_from_path(path: str) -> str | None:
    match = re.search(r"/([0-9a-fA-F-]{16,})/?(?:status|result|stream|pdf)?$", path)
    return match.group(1) if match else None


def _project_id_from_scope(scope: dict[str, Any]) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == b"x-skoleverksted-project":
            candidate = value.decode("utf-8", errors="ignore").strip()
            if re.fullmatch(r"[0-9a-fA-F]{32}", candidate):
                return candidate
    return None


def _compact_content(payload: dict[str, Any]) -> str:
    ignored = {"pdf_base64", "pdfBase64"}
    compact = {key: value for key, value in payload.items() if key not in ignored}
    return json.dumps(compact, ensure_ascii=False, default=str)[:100_000]


def _has_quality_content(payload: dict[str, Any]) -> bool:
    return any(payload.get(key) for key in (
        "text", "basis_text", "worksheet", "full_document", "fullDocument", "latex", "content"
    ))


def _quality_from_payload(module: str, payload: dict[str, Any]) -> dict[str, Any]:
    verification = payload.get("math_verification") or payload.get("mathVerification") or {}
    sources = payload.get("sources") or []
    if not sources and payload.get("source_name"):
        sources = [str(payload["source_name"])]
    goals = payload.get("competency_goals") or payload.get("competencyGoals") or []
    passport = build_quality_passport(QualityPassportRequest(
        module=module,
        title=str(payload.get("title") or payload.get("topic") or "Generert læringsprodukt"),
        content=_compact_content(payload),
        sources=[str(source) for source in sources if source],
        competency_goals=[str(goal) for goal in goals if goal],
        has_answer_key=payload.get("include_solutions") or payload.get("has_answer_key"),
        compiled=payload.get("latex_compiled") if "latex_compiled" in payload else None,
        math_incorrect=verification.get("claims_incorrect") if isinstance(verification, dict) else None,
        math_unparseable=verification.get("claims_unparseable") if isinstance(verification, dict) else None,
        prompt_version=str(payload.get("prompt_version") or "domain-legacy"),
    ))
    return passport.model_dump()


class JobTelemetryMiddleware:
    """Record domain job responses without coupling the three domain apps.

    This pure ASGI middleware observes JSON responses while forwarding every
    byte unchanged, including SSE and file streams. Domain job stores remain
    authoritative; the platform database is a durable cross-module index.
    """

    def __init__(self, app: Callable[..., Awaitable[None]]):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Any], send: Callable[..., Any]) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        module = _module_for_path(path)
        if module is None:
            await self.app(scope, receive, send)
            return

        content_type = ""
        status_code = 200
        chunks: list[bytes] = []

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal content_type, status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 200))
                for key, value in message.get("headers", []):
                    if key.lower() == b"content-type":
                        content_type = value.decode("latin-1")
                        break
            elif message.get("type") == "http.response.body" and (
                "application/json" in content_type or "text/event-stream" in content_type
            ):
                body = message.get("body", b"")
                if sum(map(len, chunks)) + len(body) <= 1_000_000:
                    chunks.append(body)
            await send(message)

        await self.app(scope, receive, send_wrapper)
        if status_code >= 500 or not chunks:
            return
        try:
            raw_body = b"".join(chunks)
            if "text/event-stream" in content_type:
                events = []
                for line in raw_body.decode("utf-8", errors="ignore").splitlines():
                    if line.startswith("data:"):
                        try:
                            events.append(json.loads(line[5:].strip()))
                        except json.JSONDecodeError:
                            continue
                terminal = next((event for event in reversed(events) if event.get("type") in {"done", "error"}), None)
                if terminal is None:
                    return
                payload = {
                    **terminal,
                    "job_id": _job_id_from_path(path),
                    "status": "completed" if terminal.get("type") == "done" else "failed",
                    "progress": 100,
                }
            else:
                payload = json.loads(raw_body)
            job_id = _job_id(payload) or _job_id_from_path(path)
            if not job_id or not isinstance(payload, dict):
                return
            store = get_platform_store()
            current = store.get_job(job_id)
            raw_status_value = payload.get("status")
            if not raw_status_value and "step" in payload:
                step = int(payload.get("step") or 0)
                total_steps = int(payload.get("total_steps") or 0)
                raw_status_value = "failed" if step < 0 else "completed" if total_steps > 0 and step >= total_steps else "running"
            raw_status = str(raw_status_value or ("failed" if status_code >= 400 else "running")).lower()
            status = _STATUS_MAP.get(raw_status, current.status if current else "generating")
            if "step" in payload and payload.get("total_steps"):
                progress_value = round(max(0, int(payload.get("step") or 0)) / int(payload["total_steps"]) * 100)
            else:
                progress_value = payload.get("progress", 100 if status in {"completed", "needs_review", "failed"} else 10)
            if isinstance(progress_value, dict):
                progress_value = progress_value.get("percent", 10)
            try:
                progress = max(0, min(100, int(progress_value)))
            except (TypeError, ValueError):
                progress = 10
            quality_payload = payload.get("json_data") if isinstance(payload.get("json_data"), dict) else payload
            quality = (
                _quality_from_payload(module, quality_payload)
                if status in {"completed", "needs_review"} and _has_quality_content(quality_payload)
                else {}
            )
            job = Job(
                id=job_id,
                module=module,
                kind=current.kind if current else "generation",
                status=status,
                progress=progress,
                message=str(payload.get("message") or payload.get("detail") or ""),
                project_id=(current.project_id if current else None) or _project_id_from_scope(scope),
                request_summary=current.request_summary if current else {},
                result_summary={"path": path, "status_code": status_code},
                quality_passport=quality or (current.quality_passport if current else {}),
                queue_position=current.queue_position if current else None,
                retryable=current.retryable if current else status in {"failed", "needs_review"},
                attempt=current.attempt if current else 1,
                created_at=current.created_at if current else utc_now(),
                updated_at=utc_now(),
            )
            store.upsert_job(job)
        except Exception:
            # Telemetry must never break a teacher-facing generation response.
            return

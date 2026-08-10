"""Durable parent/child workers for TeachingPackage.

The HTTP layer only registers jobs and returns. Workers always re-read the
canonical package and use a compare-and-swap token before writing output.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Iterable

from .models import Job, RepairChange, TeachingArtifact, TeachingArtifactFile, TeachingPackage
from .quality_gate import run_quality_pipeline
from .queue import get_durable_job_queue
from .store import StaleTeachingArtifactError, get_platform_store
from .teaching_package import (
    aggregate_package_status,
    build_quality,
    content_digest,
    draft_content,
    source_notes,
    with_revision_digest,
)
from .teaching_package_renderer import artifact_file_metadata, render_artifact
from .truth import audit_truth


class TeachingJobCancelled(RuntimeError):
    pass


MAX_QUALITY_REPAIR_ROUNDS = 3


def _now_epoch(value: str) -> float:
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return time.time()


def _active(job_id: str) -> bool:
    job = get_platform_store().get_job(job_id)
    return job is not None and job.status not in {"cancelled", "failed", "superseded", "completed"}


def _set_artifact_claim(package: TeachingPackage, artifact_id: str, job: Job) -> TeachingPackage:
    artifact = next(item for item in package.artifacts if item.id == artifact_id)
    artifact.status = "generating"
    artifact.generation_token = f"{job.id}:{job.attempt}"
    artifact.artifact_job_id = job.id
    artifact.package_revision = package.package_revision
    artifact.updated_at = datetime.now(timezone.utc).isoformat()
    package.status = "generating"
    package.package_job_id = package.package_job_id or job.id
    package.updated_at = artifact.updated_at
    return with_revision_digest(package)


def _quality_changes(content_after: str, passport) -> list[RepairChange]:
    changes: list[RepairChange] = []
    for claim in passport.claims:
        if claim.status == "verified":
            continue
        applied = bool(claim.exact_text and claim.exact_text not in content_after)
        changes.append(
            RepairChange(
                issue_id=claim.id,
                action=claim.action,
                result="applied" if applied else "manual_review",
                before=claim.exact_text or claim.claim,
                after=claim.replacement if applied else "",
                reason=(
                    "Påstanden ble endret av fagredaktøren og kontrolleres på nytt."
                    if applied
                    else "Påstanden kunne ikke endres sikkert automatisk."
                ),
                source_refs=claim.source_urls,
            )
        )
    return changes


def _verify_content(
    package: TeachingPackage,
    artifact: TeachingArtifact,
    *,
    repair: bool = True,
) -> TeachingArtifact:
    """Submit exact artifact text to the one global verification engine."""
    original = artifact.content_markdown
    result = run_quality_pipeline(
        generator_id=f"platform.teaching_package.{artifact.artifact_type}",
        content=original,
        topic=package.plan.theme,
        subject=package.subject,
        level=package.level,
        provided_sources=artifact.sources or package.plan.sources,
        max_rounds=MAX_QUALITY_REPAIR_ROUNDS if repair else 1,
        audit=audit_truth,
    )
    content = result.approved_content
    final_passport = result.passport
    if content != artifact.content_markdown:
        artifact.previous_content_markdown = artifact.content_markdown
        artifact.revision_count += 1
    artifact.content_markdown = content
    artifact.content_revision = content_digest(content)
    artifact.truth_passport = final_passport
    if final_passport.sources:
        artifact.sources = list(final_passport.sources)
    artifact.quality_rounds = [*artifact.quality_rounds, *result.rounds][-20:]
    artifact.quarantine = [*artifact.quarantine, *result.quarantine][-120:]
    artifact.quality_run_count += 1
    artifact.quality_stop_reason = result.stop_reason
    artifact.quality_passport = build_quality(package, artifact, compiled=False)
    artifact.source_quality_notes = source_notes(artifact.sources or package.plan.sources)
    artifact.verification_notes = list(final_passport.limitations)
    if final_passport.status == "verification_failed":
        artifact.status = "verification_failed"
    else:
        # source_unavailable is a repair/review state, never a permanent dead end.
        artifact.status = "needs_review"
    return artifact


def _render_and_verify(package: TeachingPackage, artifact: TeachingArtifact) -> tuple[TeachingArtifact, dict[str, bytes]]:
    artifact = _verify_content(package, artifact)
    rendered = render_artifact(package, artifact)
    artifact.files = [
        # Metadata is validated by Pydantic in the store call.
        # The package revision is part of the storage key and ZIP allowlist.
        TeachingArtifactFile.model_validate(item)
        for item in artifact_file_metadata(package, artifact, rendered)
    ]
    artifact.artifact_version += 1
    artifact.quality_passport = build_quality(package, artifact, compiled=True)
    return artifact, rendered


def _finish_job(job_id: str, *, message: str, status: str = "completed", retryable: bool = False, summary: dict[str, object] | None = None, quality: object | None = None) -> None:
    store = get_platform_store()
    store.update_job_state(job_id, status=status, message=message, progress=100, retryable=retryable)
    if summary is not None:
        quality_payload = quality.model_dump(mode="json") if hasattr(quality, "model_dump") else None
        store.update_job_result_summary(job_id, summary, quality_passport=quality_payload)


def _fail_artifact(package_id: str, artifact_id: str, job: Job, status: str, reason: str) -> None:
    store = get_platform_store()
    current = store.teaching_artifact(package_id, artifact_id)
    if current is not None:
        package, artifact = current
        if artifact.generation_token == f"{job.id}:{job.attempt}":
            artifact.status = status  # type: ignore[assignment]
            artifact.generation_token = None
            artifact.updated_at = datetime.now(timezone.utc).isoformat()
            package.status = aggregate_package_status(package)
            store.save_teaching_package(with_revision_digest(package))
    _finish_job(
        job.id,
        message="Artefaktet kunne ikke ferdigstilles. Se neste handling i pakken.",
        status="failed",
        retryable=True,
        summary={
            "queue_wait_ms": max(0, round((time.time() - _now_epoch(job.created_at)) * 1000)),
            "generation_ms": 0,
            "retry_count": max(0, job.attempt - 1),
            "failure_reason": reason,
        },
    )


def run_artifact_job(
    package_id: str,
    artifact_id: str,
    job_id: str,
    *,
    verify_only: bool = False,
    quality_repair: bool = True,
) -> None:
    store = get_platform_store()
    gate = get_durable_job_queue()
    job = store.get_job(job_id)
    if job is None:
        return
    started = time.time()
    try:
        with gate.claim(job_id, auto_complete=False):
            job = store.get_job(job_id)
            if job is None or job.status == "cancelled":
                raise TeachingJobCancelled()
            current = store.teaching_artifact(package_id, artifact_id)
            if current is None:
                raise KeyError("Artefaktet finnes ikke.")
            package, artifact = current
            token = artifact.generation_token
            if not token:
                if artifact.status == "cancelled":
                    raise TeachingJobCancelled()
                raise StaleTeachingArtifactError(f"{job.id}:{job.attempt}", "")
            if not verify_only:
                artifact.content_markdown = draft_content(package, artifact.artifact_type)
                artifact.content_revision = content_digest(artifact.content_markdown)
                artifact.previous_content_markdown = artifact.previous_content_markdown or ""
            artifact = _verify_content(package, artifact, repair=quality_repair)
            rendered: dict[str, bytes] = {}
            if not verify_only or quality_repair or not artifact.files:
                rendered = render_artifact(package, artifact)
                artifact.files = [
                    TeachingArtifactFile.model_validate(item)
                    for item in artifact_file_metadata(package, artifact, rendered)
                ]
                artifact.artifact_version += 1
                artifact.quality_passport = build_quality(package, artifact, compiled=True)
                if artifact.status == "needs_review" and artifact.quality_passport.overall_status == "failed":
                    artifact.status = "language_quality_failed"
            artifact.generation_token = None
            artifact.updated_at = datetime.now(timezone.utc).isoformat()
            package_status = aggregate_package_status(package)
            saved = (
                store.cas_update_teaching_artifact(
                    package_id,
                    artifact_id,
                    expected_generation_token=token,
                    artifact=artifact,
                    rendered=rendered,
                    package_status=package_status,
                )
                if not verify_only
                else _save_verified_if_current(package, artifact, token, job_id)
            )
            _finish_job(
                job_id,
                message="Artefaktet er ferdig kontrollert og kan vurderes av læreren.",
                summary={
                    "queue_wait_ms": max(0, round((started - _now_epoch(job.created_at)) * 1000)),
                    "generation_ms": max(0, round((time.time() - started) * 1000)),
                    "retry_count": max(0, job.attempt - 1),
                    "failure_reason": "",
                },
                quality=artifact.quality_passport,
            )
    except TeachingJobCancelled:
        _fail_artifact(package_id, artifact_id, job, "cancelled", "cancelled")
    except StaleTeachingArtifactError:
        _finish_job(
            job_id,
            message="Jobben ble foreldet fordi læreren endret artefaktet.",
            status="superseded",
            retryable=False,
            summary={"queue_wait_ms": 0, "generation_ms": max(0, round((time.time() - started) * 1000)), "retry_count": max(0, job.attempt - 1), "failure_reason": "superseded"},
        )
    except Exception:
        _fail_artifact(package_id, artifact_id, job, "generation_incomplete" if not verify_only else "verification_failed", "artifact_generation_failed" if not verify_only else "truth_verification_failed")


def _save_verified_if_current(package: TeachingPackage, artifact: TeachingArtifact, token: str, job_id: str) -> TeachingPackage:
    store = get_platform_store()
    current = store.teaching_artifact(package.id, artifact.id)
    if current is None:
        raise KeyError("Artefaktet finnes ikke.")
    stored_package, stored_artifact = current
    if stored_artifact.generation_token != token:
        raise StaleTeachingArtifactError(token, stored_artifact.generation_token or "")
    index = stored_package.artifacts.index(stored_artifact)
    stored_package.artifacts[index] = artifact
    stored_package.status = aggregate_package_status(stored_package)
    return store.save_teaching_package(with_revision_digest(stored_package))


def _run_package(package_id: str, package_job_id: str, artifact_job_ids: Iterable[str]) -> None:
    store = get_platform_store()
    parent = store.get_job(package_job_id)
    started = time.time()
    if parent is None:
        return
    store.update_job_state(package_job_id, status="planning", message="Pakken klargjøres …", progress=2, retryable=True)
    for artifact_job_id in artifact_job_ids:
        job = store.get_job(artifact_job_id)
        if job is None:
            continue
        if store.get_job(package_job_id) and store.get_job(package_job_id).status == "cancelled":
            break
        run_artifact_job(package_id, job.request_summary.get("artifact_id", ""), artifact_job_id)
        package = store.get_teaching_package(package_id)
        if package:
            completed = sum(1 for artifact in package.artifacts if artifact.status not in {"planned", "generating"})
            store.update_job_state(package_job_id, status="generating", message=f"{completed} av {len(package.artifacts)} artefakter er behandlet.", progress=min(95, round(completed * 95 / max(1, len(package.artifacts)))), retryable=True)
    package = store.get_teaching_package(package_id)
    parent_state = store.get_job(package_job_id)
    if package:
        package.status = aggregate_package_status(package)
        package.package_job_id = package_job_id
        store.save_teaching_package(with_revision_digest(package))
    failed = [job_id for job_id in artifact_job_ids if (store.get_job(job_id) or Job(id=job_id, module="platform")).status in {"failed", "superseded", "cancelled"}]
    parent_cancelled = parent_state is not None and parent_state.status == "cancelled"
    _finish_job(
        package_job_id,
        message="Pakken er behandlet. Kontroller artefaktene før godkjenning." if failed else "Alle artefaktene er generert og kontrollert.",
        status="cancelled" if parent_cancelled else "completed",
        retryable=parent_cancelled,
        summary={
            "package_total_ms": max(0, round((time.time() - started) * 1000)),
            "artifact_count": len(list(artifact_job_ids)),
            "failed_artifact_count": len(failed),
            "failure_reason": "cancelled" if parent_cancelled else ("partial_artifact_failure" if failed else ""),
        },
    )


def start_package_worker(package_id: str, package_job_id: str, artifact_job_ids: list[str]) -> None:
    threading.Thread(
        target=_run_package,
        args=(package_id, package_job_id, artifact_job_ids),
        name=f"teaching-package-{package_id[:8]}",
        daemon=True,
    ).start()


def start_artifact_worker(
    package_id: str,
    artifact_id: str,
    job_id: str,
    *,
    verify_only: bool = False,
    quality_repair: bool = True,
) -> None:
    threading.Thread(
        target=run_artifact_job,
        args=(package_id, artifact_id, job_id),
        kwargs={"verify_only": verify_only, "quality_repair": quality_repair},
        name=f"teaching-artifact-{artifact_id[:8]}",
        daemon=True,
    ).start()


def recover_teaching_package_jobs() -> int:
    store = get_platform_store()
    recovered = 0
    for package in store.list_teaching_packages(limit=500):
        changed = False
        if package.package_job_id:
            parent = store.get_job(package.package_job_id)
            if parent and parent.status not in {"completed", "failed", "cancelled", "superseded"} and any(
                artifact.status == "generating" or artifact.generation_token for artifact in package.artifacts
            ):
                store.update_job_state(
                    parent.id,
                    status="needs_review",
                    message="Pakkejobben ble gjenopprettet etter omstart; uferdige artefakter må kjøres på nytt.",
                    progress=100,
                    retryable=True,
                )
        for artifact in package.artifacts:
            if artifact.status == "generating" or artifact.generation_token:
                if artifact.artifact_job_id:
                    job = store.get_job(artifact.artifact_job_id)
                    if job and job.status not in {"completed", "failed", "cancelled", "superseded"}:
                        store.update_job_state(
                            job.id,
                            status="needs_review",
                            message="Jobben ble gjenopprettet etter omstart; artefaktet må kontrolleres på nytt.",
                            progress=100,
                            retryable=True,
                        )
                artifact.status = "generation_incomplete"
                artifact.generation_token = None
                artifact.updated_at = datetime.now(timezone.utc).isoformat()
                changed = True
                recovered += 1
        if changed:
            package.status = "needs_review"
            store.save_teaching_package(with_revision_digest(package))
    return recovered


def cancel_teaching_job(job_id: str) -> None:
    store = get_platform_store()
    job = store.get_job(job_id)
    if job is None:
        return
    get_durable_job_queue().cancel(job_id)
    for package in store.list_teaching_packages(limit=500):
        changed = False
        if package.package_job_id == job_id:
            for artifact in package.artifacts:
                if artifact.status == "generating":
                    if artifact.artifact_job_id:
                        child = store.get_job(artifact.artifact_job_id)
                        if child and child.status not in {"completed", "failed", "cancelled", "superseded"}:
                            get_durable_job_queue().cancel(child.id)
                    artifact.status = "cancelled"
                    artifact.generation_token = None
                    changed = True
        for artifact in package.artifacts:
            if artifact.artifact_job_id == job_id and artifact.status == "generating":
                artifact.status = "cancelled"
                artifact.generation_token = None
                changed = True
        if changed:
            package.status = aggregate_package_status(package)
            store.save_teaching_package(with_revision_digest(package))

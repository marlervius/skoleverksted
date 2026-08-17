"""Regression coverage for terminal Norsklæring generation failures."""

from __future__ import annotations

import json

import pytest

from ScriptoriumFOV.backend import main
from ScriptoriumFOV.backend.errors import (
    ModelRateLimitError,
    ModelResponseInvalidError,
    ModelTimeoutError,
)
from ScriptoriumFOV.backend.generation_contract import (
    PIPELINE_STEPS,
    classify_model_error,
    validate_model_outputs,
)
from ScriptoriumFOV.backend.progress_store import clear_progress, get_progress, initialize_progress


def _verified_content() -> dict:
    return {
        "topic": "Arbeidsliv",
        "subject": "Norsk",
        "level": "A2.1",
        "text": "Arbeidslivet har regler som beskytter arbeidstakere.",
        "worksheet": "a) VIKTIGE BEGREPER\nArbeidstaker: en person som arbeider.",
        "language_exercises": None,
        "truth_passport": {
            "status": "verified",
            "content_revision": "revision",
            "version": "2.0",
        },
        "verification_content": "Kontrollert tekst",
        "quarantine": [],
        "quality_rounds": [],
        "quality_stop_reason": "verified",
    }


def _request(image_mode: str = "none") -> main.LessonRequest:
    return main.LessonRequest(
        topic="Arbeidsliv",
        subject="Norsk",
        level="A2.1",
        image_mode=image_mode,
    )


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (TimeoutError("provider timed out"), "model_timeout"),
        (RuntimeError("429 RESOURCE_EXHAUSTED"), "model_rate_limited"),
        (RuntimeError("404 model gemini-unknown not found"), "model_not_found"),
    ],
)
def test_model_errors_are_classified_without_exposing_provider_text(exc, code):
    classified = classify_model_error(exc)
    assert classified.code == code
    assert "gemini-unknown" not in classified.public_message


@pytest.mark.parametrize(
    ("text", "worksheet", "language", "code"),
    [
        ("", "Oppgave", None, "model_response_empty"),
        ("Tekst", "", None, "model_response_missing_field"),
        ("Tekst", "Oppgave", "{not-json", "model_response_invalid"),
        ("Tekst", "Oppgave", json.dumps(["ikke", "objekt"]), "model_response_invalid"),
    ],
)
def test_invalid_model_output_is_rejected_before_quality_or_export(text, worksheet, language, code):
    with pytest.raises(ModelResponseInvalidError) as caught:
        validate_model_outputs(text=text, worksheet=worksheet, language_exercises_raw=language)
    assert caught.value.code == code


@pytest.mark.parametrize(
    "exc",
    [
        ModelResponseInvalidError("model_response_empty"),
        ModelTimeoutError(),
        ModelRateLimitError(external_status=429),
    ],
)
def test_step_one_failure_is_terminal_and_never_exportable(monkeypatch, exc):
    job_id = f"step-one-{exc.code}"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="request-step-one")
    monkeypatch.setattr(main, "generate_lesson_content", lambda **_kwargs: (_ for _ in ()).throw(exc))

    try:
        main.generate_lesson_background(job_id, _request())
        state = get_progress(job_id)
        assert state["job_status"] == "failed"
        assert state["terminal_status"] == "failed"
        assert state["event_type"] == "error"
        assert state["error"]["code"] == exc.code
        assert state["error"]["step_name"] == PIPELINE_STEPS[0].name
        assert "pdf_bytes" not in state
        assert "artifact" not in state
        with pytest.raises(main.HTTPException) as blocked:
            main.download_pdf(job_id, None)
        assert blocked.value.status_code == 202
    finally:
        clear_progress(job_id)


def test_ai_image_failure_preserves_verified_text_and_requests_user_action(monkeypatch):
    job_id = "image-needs-action"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="request-image")
    monkeypatch.setattr(main, "generate_lesson_content", lambda **_kwargs: _verified_content())
    monkeypatch.setattr(main, "_materialize_pedagogical_image", lambda *_args, **_kwargs: (None, None, "", ""))

    try:
        main.generate_lesson_background(job_id, _request("ai"))
        state = get_progress(job_id)
        assert state["job_status"] == "needs_user_action"
        assert state["event_type"] == "user_action_required"
        assert state["content_checkpoint"]["text"] == _verified_content()["text"]
        assert state["error"]["code"] == "image_generation_failed"
        assert set(state["available_actions"]) == {
            "retry_image",
            "continue_without_image",
            "choose_commons",
            "upload_image",
            "cancel",
        }
        assert "pdf_bytes" not in state
    finally:
        clear_progress(job_id)


def test_continue_without_image_reuses_checkpoint_not_text_model(monkeypatch):
    job_id = "image-resume-none"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="request-resume")
    checkpoint = _verified_content()
    main.merge_progress(
        job_id,
        content_checkpoint=checkpoint,
        request_checkpoint=_request("ai").model_dump(mode="json"),
    )
    calls = {"model": 0}
    monkeypatch.setattr(main, "generate_lesson_content", lambda **_kwargs: calls.__setitem__("model", 1))
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **_kwargs: b"%PDF-1.7\nvalid")
    monkeypatch.setattr(
        main,
        "validate_pdf_artifact",
        lambda pdf, filename: main.ValidatedArtifact(
            content=pdf,
            content_type="application/pdf",
            filename=filename,
            kind="student_pdf",
        ),
    )
    monkeypatch.setattr(main, "_cleanup_image", lambda _path: None)

    try:
        main.resume_lesson_from_checkpoint_background(job_id, image_mode="none")
        state = get_progress(job_id)
        assert calls["model"] == 0
        assert state["job_status"] == "completed"
        assert state["artifact"]["content_type"] == "application/pdf"
    finally:
        clear_progress(job_id)


def test_cancelled_job_does_not_start_model_or_image(monkeypatch):
    job_id = "cancel-before-start"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="request-cancel")
    main.cancel_generation_state(job_id)
    calls: list[str] = []
    monkeypatch.setattr(main, "generate_lesson_content", lambda **_kwargs: calls.append("model"))
    monkeypatch.setattr(main, "_materialize_pedagogical_image", lambda *_args, **_kwargs: calls.append("image"))

    try:
        main.generate_lesson_background(job_id, _request("ai"))
        state = get_progress(job_id)
        assert calls == []
        assert state["job_status"] == "cancelled"
        assert state["event_type"] == "cancelled"
    finally:
        clear_progress(job_id)


def test_terminal_event_iterator_emits_error_for_failed_job():
    job_id = "sse-terminal-error"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="request-sse")
    main._mark_generation_failed(job_id, ModelTimeoutError(), 4, step=PIPELINE_STEPS[0])

    try:
        events = list(main.iter_generation_events(job_id, after=0, wait_timeout=0.01))
        assert events[-1]["type"] == "error"
        assert events[-1]["status"] == "failed"
        assert events[-1]["request_id"] == "request-sse"
    finally:
        clear_progress(job_id)

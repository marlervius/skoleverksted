"""Regression tests for the Norsklæring generation completion handshake."""

from ScriptoriumFOV.backend import main
from ScriptoriumFOV.backend.progress_store import clear_progress, initialize_progress


def test_pdf_is_materialized_before_step_four_is_published(monkeypatch):
    """Reproduce the production race between the final progress poll and PDF storage."""

    events: list[tuple[str, object]] = []
    state: dict = {}

    monkeypatch.setattr(
        main,
        "generate_lesson_content",
        lambda **_kwargs: {
            "text": "Norge er et land i Europa.",
            "worksheet": "a) VIKTIGE BEGREPER\nEuropa: et kontinent.",
        },
    )
    monkeypatch.setattr(
        main,
        "_materialize_pedagogical_image",
        lambda *_args, **_kwargs: (None, None, "", ""),
    )
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **_kwargs: b"%PDF-1.7\nvalid")
    monkeypatch.setattr(main, "validate_pdf_artifact", lambda pdf, filename: main.ValidatedArtifact(
        content=pdf,
        content_type="application/pdf",
        filename=filename,
        kind="student_pdf",
    ))
    monkeypatch.setattr(main, "_cleanup_image", lambda _path: None)

    def record_progress(generation_id, step, total_steps, message, **kwargs):
        state.update({"job_id": generation_id, "step": step, "total_steps": total_steps, "message": message})
        state.update(kwargs)
        events.append(("progress", {"generation_id": generation_id, "step": step, "message": message}))

    def record_merge(generation_id, **fields):
        state.update(fields)
        events.append(("artifact", {"generation_id": generation_id, **fields}))

    monkeypatch.setattr(main, "update_progress", record_progress)
    monkeypatch.setattr(main, "merge_progress", record_merge)
    monkeypatch.setattr(main, "get_progress", lambda _generation_id: dict(state))

    request = main.LessonRequest(
        topic="Arbeidsliv",
        subject="Norsk",
        level="A2.1",
    )

    main.generate_lesson_background("job-race", request)

    artifact_index = next(i for i, (kind, _payload) in enumerate(events) if kind == "artifact")
    step_four_index = next(
        i
        for i, (kind, payload) in enumerate(events)
        if kind == "progress" and payload["step"] == 4
    )
    assert artifact_index < step_four_index


def test_invalid_pdf_never_publishes_completed(monkeypatch):
    job_id = "job-invalid-pdf"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="req-invalid")
    monkeypatch.setattr(
        main,
        "generate_lesson_content",
        lambda **_kwargs: {"text": "Tekst", "worksheet": "Oppgave"},
    )
    monkeypatch.setattr(
        main,
        "_materialize_pedagogical_image",
        lambda *_args, **_kwargs: (None, None, "", ""),
    )
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **_kwargs: b"not a pdf")
    monkeypatch.setattr(main, "_cleanup_image", lambda _path: None)

    try:
        request = main.LessonRequest(topic="Arbeidsliv", subject="Norsk", level="A2.1")
        main.generate_lesson_background(job_id, request)
        state = main.get_progress(job_id)
        assert state["job_status"] == "failed"
        assert state["status"] == "failed"
        assert "artifact" not in state
        assert "pdf_bytes" not in state
        assert state["last_event"]["type"] == "failed"
    finally:
        clear_progress(job_id)

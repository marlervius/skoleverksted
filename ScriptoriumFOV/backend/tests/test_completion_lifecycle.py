from ScriptoriumFOV.backend.progress_store import (
    clear_progress,
    get_progress,
    initialize_progress,
    is_pdf_ready,
    merge_progress,
    publish_event,
    update_progress,
)


def test_artifact_ready_is_not_terminal_until_done_is_published():
    job_id = "lifecycle-test"
    clear_progress(job_id)
    try:
        initialize_progress(job_id, 4, "Starter", request_id="req-123")
        pdf = b"%PDF-1.7" + b"x" * 300
        artifact = {
            "id": "lifecycle-test:student_pdf:abc",
            "job_id": job_id,
            "kind": "student_pdf",
            "filename": "Arbeidsliv.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(pdf),
            "preview_url": "/api/norsk/download-pdf/lifecycle-test?preview=true",
            "download_url": "/api/norsk/download-pdf/lifecycle-test",
        }
        merge_progress(job_id, pdf_bytes=pdf, artifact=artifact)
        publish_event(job_id, "artifact_ready", artifact=artifact)
        state = get_progress(job_id)
        assert state["job_status"] == "running"
        assert not is_pdf_ready(state)

        update_progress(job_id, 4, 4, "Artefaktet er kontrollert.")
        publish_event(job_id, "done", job_status="completed", artifact=artifact)
        state = get_progress(job_id)
        assert state["status"] == "completed"
        assert is_pdf_ready(state)
        event_types = [event["type"] for event in state["events"]]
        assert event_types.index("artifact_ready") < event_types.index("done")
        assert event_types[-1] == "done"
    finally:
        clear_progress(job_id)

from ScriptoriumFOV.backend.progress_store import (
    cancel_progress,
    clear_progress,
    get_progress,
    initialize_progress,
    is_json_preview_ready,
    update_progress,
)


def test_json_preview_is_not_ready_during_image_search() -> None:
    assert not is_json_preview_ready(
        {
            "step": 2,
            "total_steps": 3,
            "json_data": {"topic": "Fotosyntese"},
        }
    )


def test_json_preview_requires_payload_at_final_step() -> None:
    assert not is_json_preview_ready({"step": 3, "total_steps": 3})
    assert is_json_preview_ready(
        {
            "step": 3,
            "total_steps": 3,
            "json_data": {"topic": "Fotosyntese"},
        }
    )


def test_cancelled_generation_is_terminal_and_late_worker_updates_are_ignored() -> None:
    job_id = "cancelled-progress-test"
    clear_progress(job_id)
    initialize_progress(job_id, 3, "Starter")
    try:
        assert cancel_progress(job_id)
        update_progress(job_id, 3, 3, "Skal ikke gjenopplive jobben", job_status="completed")
        state = get_progress(job_id)
        assert state["job_status"] == "cancelled"
        assert state["terminal_status"] == "cancelled"
        assert state["last_event"]["type"] == "cancelled"
    finally:
        clear_progress(job_id)

from ScriptoriumFOV.backend.progress_store import is_json_preview_ready


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

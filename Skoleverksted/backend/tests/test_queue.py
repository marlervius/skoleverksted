from Skoleverksted.backend.platform.queue import _RedisJobLease
from Skoleverksted.backend.platform.queue import DurableJobGate
from Skoleverksted.backend.platform.store import PlatformStore


def test_job_lease_is_safe_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    lease = _RedisJobLease(1)

    assert lease.configured is False
    with lease.claim("test-job"):
        pass


def test_review_job_is_terminal_and_survives_queue_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = PlatformStore(tmp_path / "platform.sqlite3")
    monkeypatch.setattr("Skoleverksted.backend.platform.queue.get_platform_store", lambda: store)
    queue = DurableJobGate()
    queue.enqueue("draft", module="matematikk", kind="generation")
    with queue.claim("draft", auto_complete=False):
        queue.needs_review("draft", message="Utkastet krever gjennomgang")
    DurableJobGate()  # Recovery must not requeue or fail a finished review draft.
    job = store.get_job("draft")
    assert job.status == "needs_review"
    assert job.progress == 100 and not job.retryable

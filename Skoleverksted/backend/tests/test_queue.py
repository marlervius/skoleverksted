from Skoleverksted.backend.platform.queue import _RedisJobLease


def test_job_lease_is_safe_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    lease = _RedisJobLease(1)

    assert lease.configured is False
    with lease.claim("test-job"):
        pass

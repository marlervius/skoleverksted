"""
Tests for sharing — access control, password, expiry.
"""

import pytest
from datetime import datetime, timedelta

from app.stores import sharing_store as share_store
from app.sharing.router import (
    ShareRequest,
    _check_link_valid,
    _check_password,
    _hash_password,
)


@pytest.fixture(autouse=True)
def clean_stores():
    share_store.all_links().clear()
    yield
    share_store.all_links().clear()


class TestPasswordHashing:
    def test_bcrypt_verify(self):
        h = _hash_password("test123")
        assert _check_password("test123", h)
        assert not _check_password("wrong", h)

    def test_different_passwords_different_hash(self):
        h1 = _hash_password("test123")
        h2 = _hash_password("test456")
        assert h1 != h2


class TestLinkValidation:
    def test_valid_link(self):
        link = {"expires_at": None, "max_views": None, "view_count": 0}
        valid, error = _check_link_valid(link)
        assert valid is True
        assert error == ""

    def test_expired_link(self):
        link = {
            "expires_at": (datetime.now() - timedelta(hours=1)).isoformat(),
            "max_views": None,
            "view_count": 0,
        }
        valid, error = _check_link_valid(link)
        assert valid is False
        assert "expired" in error.lower()

    def test_max_views_exceeded(self):
        link = {"expires_at": None, "max_views": 5, "view_count": 5}
        valid, error = _check_link_valid(link)
        assert valid is False
        assert "views" in error.lower()


class TestShareRequest:
    def test_valid_request(self):
        req = ShareRequest(resource_type="generation", resource_id="abc123")
        assert req.resource_type == "generation"

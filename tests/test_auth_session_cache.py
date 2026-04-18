"""Tests for src/argus/core/auth.py — session cache TTL and invalidation."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


def _reset_cache():
    from argus.core import auth
    auth._session_cache.clear()


@pytest.fixture(autouse=True)
def clean_cache():
    _reset_cache()
    yield
    _reset_cache()


class TestSessionCacheTTL:
    def test_session_is_cached_on_first_call(self):
        from argus.core.auth import get_session
        with patch("boto3.Session") as mock_session_cls:
            mock_session_cls.return_value = MagicMock()
            s1 = get_session(profile=None, region="us-east-1")
            s2 = get_session(profile=None, region="us-east-1")
        assert s1 is s2
        assert mock_session_cls.call_count == 1

    def test_expired_cache_entry_creates_new_session(self):
        from argus.core import auth
        from argus.core.auth import get_session, _SESSION_TTL
        with patch("boto3.Session") as mock_session_cls:
            mock1 = MagicMock()
            mock2 = MagicMock()
            mock_session_cls.side_effect = [mock1, mock2]

            s1 = get_session(profile=None, region="us-east-1")
            # Manually backdate the cache entry to simulate TTL expiry
            key = (None, "us-east-1")
            auth._session_cache[key] = (s1, time.monotonic() - _SESSION_TTL - 1)

            s2 = get_session(profile=None, region="us-east-1")

        assert s1 is not s2
        assert mock_session_cls.call_count == 2

    def test_fresh_cache_entry_is_reused(self):
        from argus.core.auth import get_session
        with patch("boto3.Session") as mock_session_cls:
            mock_session_cls.return_value = MagicMock()
            get_session(profile=None, region="us-east-1")
            get_session(profile=None, region="us-east-1")
        assert mock_session_cls.call_count == 1

    def test_different_profiles_are_cached_independently(self):
        from argus.core.auth import get_session
        with patch("boto3.Session") as mock_session_cls:
            mock_session_cls.side_effect = [MagicMock(), MagicMock()]
            s1 = get_session(profile="dev", region="us-east-1")
            s2 = get_session(profile="prod", region="us-east-1")
        assert s1 is not s2
        assert mock_session_cls.call_count == 2

    def test_different_regions_are_cached_independently(self):
        from argus.core.auth import get_session
        with patch("boto3.Session") as mock_session_cls:
            mock_session_cls.side_effect = [MagicMock(), MagicMock()]
            s1 = get_session(profile=None, region="us-east-1")
            s2 = get_session(profile=None, region="us-west-2")
        assert s1 is not s2

    def test_reset_session_cache_clears_all_entries(self):
        from argus.core.auth import get_session, reset_session_cache
        with patch("boto3.Session") as mock_session_cls:
            mock_session_cls.side_effect = [MagicMock(), MagicMock()]
            get_session(profile=None, region="us-east-1")
            reset_session_cache()
            get_session(profile=None, region="us-east-1")
        assert mock_session_cls.call_count == 2

    def test_invalidate_session_removes_specific_entry(self):
        from argus.core.auth import get_session, invalidate_session
        with patch("boto3.Session") as mock_session_cls:
            mock_session_cls.side_effect = [MagicMock(), MagicMock(), MagicMock()]
            get_session(profile="dev", region="us-east-1")
            get_session(profile="prod", region="us-east-1")
            invalidate_session(profile="dev", region="us-east-1")
            # dev should be recreated; prod should still be cached
            get_session(profile="dev", region="us-east-1")
            get_session(profile="prod", region="us-east-1")
        assert mock_session_cls.call_count == 3  # dev×2, prod×1

    def test_invalidate_nonexistent_entry_is_safe(self):
        from argus.core.auth import invalidate_session
        # Should not raise
        invalidate_session(profile="ghost", region="us-east-1")

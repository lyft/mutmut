"""Tests for mutmut.models.cache_status module."""

from mutmut.models.cache_status import CACHE_STATUS_EMOJI
from mutmut.models.cache_status import CacheStatus


class TestCacheStatusEnum:
    """Tests for CacheStatus enum.

    mostly needed for the UI to display the statuses correctly
    """

    def test_enum_values(self):
        """Test that all expected enum values exist."""
        assert CacheStatus.CACHED.value == "cached"
        assert CacheStatus.STALE_DEPENDENCY.value == "stale"
        assert CacheStatus.INVALID.value == "invalid"

    def test_str_returns_value(self):
        """Test that __str__ returns the value."""
        assert str(CacheStatus.CACHED) == "cached"
        assert str(CacheStatus.STALE_DEPENDENCY) == "stale"
        assert str(CacheStatus.INVALID) == "invalid"

    def test_is_str_subclass(self):
        """Test that CacheStatus is a str subclass for easy serialization."""
        assert isinstance(CacheStatus.CACHED, str)
        assert CacheStatus.CACHED == "cached"


class TestCacheStatusComparison:
    """Tests for CacheStatus comparison methods."""

    def test_cached_less_than_stale(self):
        """CACHED should be less severe than STALE_DEPENDENCY."""
        assert CacheStatus.CACHED < CacheStatus.STALE_DEPENDENCY

    def test_stale_less_than_invalid(self):
        """STALE_DEPENDENCY should be less severe than INVALID."""
        assert CacheStatus.STALE_DEPENDENCY < CacheStatus.INVALID

    def test_cached_less_than_invalid(self):
        """CACHED should be less severe than INVALID."""
        assert CacheStatus.CACHED < CacheStatus.INVALID

    def test_same_status_not_less_than(self):
        """Same status should not be less than itself."""
        assert not CacheStatus.CACHED < CacheStatus.CACHED
        assert not CacheStatus.INVALID < CacheStatus.INVALID

    def test_invalid_not_less_than_others(self):
        """INVALID should not be less than any other status."""
        assert not CacheStatus.INVALID < CacheStatus.CACHED
        assert not CacheStatus.INVALID < CacheStatus.STALE_DEPENDENCY


class TestCacheStatusWorst:
    """Tests for CacheStatus.worst() method."""

    def test_worst_of_same_returns_same(self):
        """Worst of same status returns that status."""
        assert CacheStatus.worst(CacheStatus.CACHED, CacheStatus.CACHED) == CacheStatus.CACHED
        assert CacheStatus.worst(CacheStatus.INVALID, CacheStatus.INVALID) == CacheStatus.INVALID

    def test_worst_returns_invalid_over_cached(self):
        """INVALID should win over CACHED."""
        assert CacheStatus.worst(CacheStatus.CACHED, CacheStatus.INVALID) == CacheStatus.INVALID
        assert CacheStatus.worst(CacheStatus.INVALID, CacheStatus.CACHED) == CacheStatus.INVALID

    def test_worst_returns_invalid_over_stale(self):
        """INVALID should win over STALE_DEPENDENCY."""
        assert CacheStatus.worst(CacheStatus.STALE_DEPENDENCY, CacheStatus.INVALID) == CacheStatus.INVALID
        assert CacheStatus.worst(CacheStatus.INVALID, CacheStatus.STALE_DEPENDENCY) == CacheStatus.INVALID

    def test_worst_returns_stale_over_cached(self):
        """STALE_DEPENDENCY should win over CACHED."""
        assert CacheStatus.worst(CacheStatus.CACHED, CacheStatus.STALE_DEPENDENCY) == CacheStatus.STALE_DEPENDENCY
        assert CacheStatus.worst(CacheStatus.STALE_DEPENDENCY, CacheStatus.CACHED) == CacheStatus.STALE_DEPENDENCY


class TestCacheStatusEmoji:
    """Tests for CACHE_STATUS_EMOJI mapping."""

    def test_all_statuses_have_emoji(self):
        """Test that all CacheStatus values have an emoji mapping."""
        for status in CacheStatus:
            assert status in CACHE_STATUS_EMOJI

    def test_emoji_values(self):
        """Test specific emoji values."""
        assert CACHE_STATUS_EMOJI[CacheStatus.CACHED] == "✓"
        assert CACHE_STATUS_EMOJI[CacheStatus.STALE_DEPENDENCY] == "⚠️"
        assert CACHE_STATUS_EMOJI[CacheStatus.INVALID] == "🚫"

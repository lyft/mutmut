"""Tests for mutmut.ui.helpers module."""

from mutmut.models.cache_status import CacheStatus
from mutmut.ui.helpers import compute_funcs_with_invalid_deps
from mutmut.ui.helpers import expand_changed_functions
from mutmut.ui.helpers import find_invalid_dependencies
from mutmut.ui.helpers import get_cache_status
from mutmut.ui.helpers import get_ordered_upstream_and_downstream_functions


class TestExpandChangedFunctions:
    """Tests for expand_changed_functions function."""

    def test_empty_changed_returns_empty(self):
        """Empty changed set returns empty set."""
        result = expand_changed_functions(set(), {"a": {"b"}})
        assert result == set()

    def test_empty_deps_returns_changed(self):
        """Empty deps returns just the changed functions."""
        result = expand_changed_functions({"foo"}, {})
        assert result == {"foo"}

    def test_single_level_expansion(self):
        """Test single level of caller expansion."""
        # foo calls bar, bar changed
        deps = {"bar": {"foo"}}
        result = expand_changed_functions({"bar"}, deps)
        assert result == {"bar", "foo"}

    def test_multi_level_expansion(self):
        """Test multi-level transitive expansion."""
        # Call chain: test -> a -> b -> c
        # c is the callee, test is the ultimate caller
        deps = {
            "c": {"b"},
            "b": {"a"},
            "a": {"test"},
        }
        result = expand_changed_functions({"c"}, deps)
        assert result == {"c", "b", "a", "test"}

    def test_multiple_callers(self):
        """Test function with multiple callers."""
        # helper is called by both foo and bar
        deps = {"helper": {"foo", "bar"}}
        result = expand_changed_functions({"helper"}, deps)
        assert result == {"helper", "foo", "bar"}

    def test_multiple_changed_functions(self):
        """Test multiple changed functions."""
        deps = {
            "a": {"caller_a"},
            "b": {"caller_b"},
        }
        result = expand_changed_functions({"a", "b"}, deps)
        assert result == {"a", "b", "caller_a", "caller_b"}

    def test_avoids_cycles(self):
        """Test that cycles don't cause infinite loops."""
        # a calls b, b calls a (cycle)
        deps = {
            "a": {"b"},
            "b": {"a"},
        }
        result = expand_changed_functions({"a"}, deps)
        assert result == {"a", "b"}

    def test_diamond_dependency(self):
        """Test diamond dependency pattern."""
        # test -> foo, test -> bar, foo -> helper, bar -> helper
        deps = {
            "helper": {"foo", "bar"},
            "foo": {"test"},
            "bar": {"test"},
        }
        result = expand_changed_functions({"helper"}, deps)
        assert result == {"helper", "foo", "bar", "test"}


class TestComputeFuncsWithInvalidDeps:
    """Tests for compute_funcs_with_invalid_deps function."""

    def test_empty_invalid_returns_empty(self):
        """Empty invalid funcs returns empty set."""
        result = compute_funcs_with_invalid_deps(set(), {"a": {"b"}})
        assert result == set()

    def test_empty_deps_returns_empty(self):
        """Empty deps returns empty set (no callers to expand to)."""
        result = compute_funcs_with_invalid_deps({"foo"}, {})
        assert result == set()

    def test_converts_mangled_names_to_raw(self):
        """Test that mangled names are converted to raw names."""
        # Deps use mangled names like "module.x_func"
        deps = {"module.x_bar": {"module.x_foo"}}
        invalid = {"module.bar"}  # Raw name
        result = compute_funcs_with_invalid_deps(invalid, deps)
        # Should find module.foo as a caller of module.bar
        # But should NOT include module.bar itself (only callers)
        assert "module.foo" in result
        assert "module.bar" not in result

    def test_transitive_expansion_with_mangled_names(self):
        """Test transitive expansion with realistic mangled names."""
        # Chain: test -> helper -> util
        deps = {
            "app.x_util": {"app.x_helper"},
            "app.x_helper": {"app.x_test"},
        }
        invalid = {"app.util"}
        result = compute_funcs_with_invalid_deps(invalid, deps)
        # Should include callers but NOT the invalid function itself
        assert "app.util" not in result
        assert "app.helper" in result
        assert "app.test" in result


class TestGetCacheStatus:
    """Tests for get_cache_status function."""

    def test_returns_invalid_when_exit_code_none(self):
        """INVALID when exit_code is None (not tested)."""
        result = get_cache_status("module.x_foo__mutmut_1", None, set())
        assert result == CacheStatus.INVALID

    def test_returns_cached_when_no_invalid_deps(self):
        """CACHED when exit_code set and no invalid deps."""
        result = get_cache_status("module.x_foo__mutmut_1", 0, set())
        assert result == CacheStatus.CACHED

    def test_returns_cached_when_empty_invalid_deps(self):
        """CACHED when exit_code set and empty invalid deps set."""
        result = get_cache_status("module.x_foo__mutmut_1", 1, set())
        assert result == CacheStatus.CACHED

    def test_returns_stale_when_in_invalid_deps(self):
        """STALE_DEPENDENCY when function is in invalid deps set."""
        funcs_with_invalid_deps = {"module.foo"}
        result = get_cache_status("module.x_foo__mutmut_1", 1, funcs_with_invalid_deps)
        assert result == CacheStatus.STALE_DEPENDENCY

    def test_returns_cached_when_not_in_invalid_deps(self):
        """CACHED when function is not in invalid deps set."""
        funcs_with_invalid_deps = {"module.bar"}
        result = get_cache_status("module.x_foo__mutmut_1", 1, funcs_with_invalid_deps)
        assert result == CacheStatus.CACHED

    def test_handles_class_method_names(self):
        """Test handling of class method mutant names."""
        funcs_with_invalid_deps = {"module.MyClass.method"}
        # Class method format: module.xǁMyClassǁmethod__mutmut_1
        result = get_cache_status("module.xǁMyClassǁmethod__mutmut_1", 1, funcs_with_invalid_deps)
        assert result == CacheStatus.STALE_DEPENDENCY

    def test_exit_code_zero_still_valid(self):
        """Test that exit_code=0 (tests passed/killed) is valid."""
        result = get_cache_status("module.x_foo__mutmut_1", 0, set())
        assert result == CacheStatus.CACHED


class TestFindInvalidDependencies:
    """Tests for find_invalid_dependencies function."""

    def test_empty_invalid_returns_empty(self):
        """Empty invalid funcs returns empty set."""
        result = find_invalid_dependencies("foo", set(), {"a": {"b"}})
        assert result == set()

    def test_empty_deps_returns_empty(self):
        """Empty deps returns empty set."""
        result = find_invalid_dependencies("foo", {"bar"}, {})
        assert result == set()

    def test_finds_direct_invalid_callee(self):
        """Test finding a direct invalid callee."""
        # foo calls bar, bar is invalid
        deps = {"module.x_bar": {"module.x_foo"}}
        invalid = {"module.bar"}
        result = find_invalid_dependencies("module.foo", invalid, deps)
        assert "module.bar" in result

    def test_finds_transitive_invalid_callee(self):
        """Test finding a transitive invalid callee."""
        # foo -> bar -> baz, baz is invalid
        deps = {
            "module.x_baz": {"module.x_bar"},
            "module.x_bar": {"module.x_foo"},
        }
        invalid = {"module.baz"}
        result = find_invalid_dependencies("module.foo", invalid, deps)
        assert "module.baz" in result

    def test_does_not_find_non_callee(self):
        """Test that non-callees are not found."""
        # foo calls bar, baz is invalid but not called by foo
        deps = {
            "module.x_bar": {"module.x_foo"},
            "module.x_baz": {"module.x_other"},
        }
        invalid = {"module.baz"}
        result = find_invalid_dependencies("module.foo", invalid, deps)
        assert "module.baz" not in result

    def test_handles_multiple_invalid_callees(self):
        """Test finding multiple invalid callees."""
        # foo calls both bar and baz, both are invalid
        deps = {
            "module.x_bar": {"module.x_foo"},
            "module.x_baz": {"module.x_foo"},
        }
        invalid = {"module.bar", "module.baz"}
        result = find_invalid_dependencies("module.foo", invalid, deps)
        assert "module.bar" in result
        assert "module.baz" in result

    def test_avoids_cycles(self):
        """Test that cycles don't cause infinite loops."""
        # foo -> bar -> foo (cycle)
        deps = {
            "module.x_bar": {"module.x_foo"},
            "module.x_foo": {"module.x_bar"},
        }
        invalid = {"module.bar"}
        result = find_invalid_dependencies("module.foo", invalid, deps)
        assert "module.bar" in result


class TestGetOrderedUpstreamAndDownstreamFunctions:
    """Tests for get_ordered_upstream_and_downstream_functions function."""

    def test_empty_deps_returns_empty(self):
        """Empty deps returns empty lists."""
        upstreams, downstreams = get_ordered_upstream_and_downstream_functions("foo", {})
        assert upstreams == []
        assert downstreams == []

    def test_finds_direct_upstream(self):
        """Test finding direct callers (upstream) with depth=1."""
        # foo is called by bar and baz
        deps = {"foo": {"bar", "baz"}}
        upstreams, downstreams = get_ordered_upstream_and_downstream_functions("foo", deps, max_depth=1)
        upstream_names = [name for name, _ in upstreams]
        assert "bar" in upstream_names
        assert "baz" in upstream_names
        # All should have depth 1
        assert all(depth == 1 for _, depth in upstreams)

    def test_finds_direct_downstream(self):
        """Test finding direct callees (downstream) with depth=1."""
        # foo calls bar and baz
        deps = {"bar": {"foo"}, "baz": {"foo"}}
        upstreams, downstreams = get_ordered_upstream_and_downstream_functions("foo", deps, max_depth=1)
        downstream_names = [name for name, _ in downstreams]
        assert "bar" in downstream_names
        assert "baz" in downstream_names

    def test_respects_max_depth_for_upstream(self):
        """Test that max_depth limits upstream traversal."""
        # Chain: test -> helper -> util -> core
        deps = {
            "core": {"util"},
            "util": {"helper"},
            "helper": {"test"},
        }
        # With depth=1, should only find util (direct caller)
        upstreams, _ = get_ordered_upstream_and_downstream_functions("core", deps, max_depth=1)
        upstream_names = [name for name, _ in upstreams]
        assert "util" in upstream_names
        assert "helper" not in upstream_names
        assert "test" not in upstream_names

    def test_respects_max_depth_for_downstream(self):
        """Test that max_depth limits downstream traversal."""
        # Chain: test calls helper, helper calls util, util calls core
        deps = {
            "helper": {"test"},
            "util": {"helper"},
            "core": {"util"},
        }
        # With depth=1, should only find helper (direct callee)
        _, downstreams = get_ordered_upstream_and_downstream_functions("test", deps, max_depth=1)
        downstream_names = [name for name, _ in downstreams]
        assert "helper" in downstream_names
        assert "util" not in downstream_names
        assert "core" not in downstream_names

    def test_unlimited_depth_finds_all_upstream(self):
        """Test that max_depth=0 (unlimited) finds all callers."""
        # Chain: test -> helper -> util -> core
        deps = {
            "core": {"util"},
            "util": {"helper"},
            "helper": {"test"},
        }
        upstreams, _ = get_ordered_upstream_and_downstream_functions("core", deps, max_depth=0)
        upstream_names = [name for name, _ in upstreams]
        assert "util" in upstream_names
        assert "helper" in upstream_names
        assert "test" in upstream_names

    def test_unlimited_depth_finds_all_downstream(self):
        """Test that max_depth=0 (unlimited) finds all callees."""
        deps = {
            "helper": {"test"},
            "util": {"helper"},
            "core": {"util"},
        }
        _, downstreams = get_ordered_upstream_and_downstream_functions("test", deps, max_depth=0)
        downstream_names = [name for name, _ in downstreams]
        assert "helper" in downstream_names
        assert "util" in downstream_names
        assert "core" in downstream_names

    def test_depth_values_are_correct(self):
        """Test that depth values reflect distance from source."""
        # Chain: test -> helper -> util
        deps = {
            "util": {"helper"},
            "helper": {"test"},
        }
        upstreams, _ = get_ordered_upstream_and_downstream_functions("util", deps, max_depth=0)
        depth_by_name = dict(upstreams)
        assert depth_by_name["helper"] == 1
        assert depth_by_name["test"] == 2

    def test_sorted_by_depth(self):
        """Test that results are sorted by depth (ascending)."""
        deps = {
            "core": {"util"},
            "util": {"helper"},
            "helper": {"test"},
        }
        upstreams, _ = get_ordered_upstream_and_downstream_functions("core", deps, max_depth=0)
        depths = [depth for _, depth in upstreams]
        assert depths == sorted(depths)

    def test_handles_cycles(self):
        """Test that cycles don't cause infinite loops."""
        # a calls b, b calls a (cycle)
        deps = {
            "a": {"b"},
            "b": {"a"},
        }
        upstreams, downstreams = get_ordered_upstream_and_downstream_functions("a", deps, max_depth=0)
        # Should find b as both upstream and downstream
        upstream_names = [name for name, _ in upstreams]
        downstream_names = [name for name, _ in downstreams]
        assert "b" in upstream_names
        assert "b" in downstream_names

    def test_does_not_include_self(self):
        """Test that the source function is not included in results."""
        deps = {"foo": {"bar"}, "bar": {"foo"}}
        upstreams, downstreams = get_ordered_upstream_and_downstream_functions("foo", deps, max_depth=0)
        upstream_names = [name for name, _ in upstreams]
        downstream_names = [name for name, _ in downstreams]
        assert "foo" not in upstream_names
        assert "foo" not in downstream_names

    def test_specific_depth_limit(self):
        """Test with a specific depth limit (e.g., 2)."""
        # Chain: test -> a -> b -> c -> d
        deps = {
            "d": {"c"},
            "c": {"b"},
            "b": {"a"},
            "a": {"test"},
        }
        upstreams, _ = get_ordered_upstream_and_downstream_functions("d", deps, max_depth=2)
        upstream_names = [name for name, _ in upstreams]
        assert "c" in upstream_names  # depth 1
        assert "b" in upstream_names  # depth 2 (but won't expand further)
        # b is at depth 2, so it's included but won't queue further expansion
        # Actually max_depth=2 means we stop adding to queue at depth < 2
        # So c (depth 1) is added and queued, b (depth 2) is added but NOT queued
        assert "a" not in upstream_names  # depth 3, not reached

"""
Test runner classes for mutmut.

This module contains the abstract TestRunner base class and concrete implementations
for pytest and hammett test frameworks.
"""

import os
from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Generator
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path

from mutmut.configuration import HotForkWarmup
from mutmut.configuration import config
from mutmut.state import state


class CollectTestsFailedException(Exception):
    """Raised when test collection fails."""


class BadTestExecutionCommandsException(Exception):
    """Raised when pytest execution fails due to bad arguments."""

    def __init__(self, pytest_args: list[str]) -> None:
        msg = f"Failed to run pytest with args: {pytest_args}. If your config sets debug=true, the original pytest error should be above."
        super().__init__(msg)


def unused(*_: object) -> None:
    """Suppress unused variable warnings."""


def strip_prefix(s: str, *, prefix: str, strict: bool = False) -> str:
    """Strip a prefix from a string."""
    if s.startswith(prefix):
        return s[len(prefix) :]
    assert strict is False, f"String '{s}' does not start with prefix '{prefix}'"
    return s


@contextmanager
def change_cwd(path: str | Path) -> Generator[None, None, None]:
    """Context manager to temporarily change the current working directory."""
    old_cwd = os.path.abspath(os.getcwd())
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def collected_test_names() -> set[str]:
    """Return the set of test names that have been collected."""
    return set(state().duration_by_test.keys())


class ListAllTestsResult:
    """Result from listing all tests in a test suite."""

    def __init__(self, *, ids: set[str]) -> None:
        assert isinstance(ids, set)
        self.ids = ids

    def clear_out_obsolete_test_names(self) -> None:
        """Remove test names that are no longer in the test suite."""
        # Import here to avoid circular dependency
        from mutmut.__main__ import save_stats

        count_before = sum(len(x) for x in state().tests_by_mangled_function_name)
        state().tests_by_mangled_function_name = defaultdict(
            set,
            **{
                k: {test_name for test_name in test_names if test_name in self.ids}
                for k, test_names in state().tests_by_mangled_function_name.items()
            },
        )
        count_after = sum(len(x) for x in state().tests_by_mangled_function_name)
        if count_before != count_after:
            print(f"Removed {count_before - count_after} obsolete test names")
            save_stats()

    def new_tests(self) -> set[str]:
        """Return test names that are new (not previously collected)."""
        return self.ids - collected_test_names()


class TestRunner(ABC):
    """Abstract base class for test runners."""

    @abstractmethod
    def run_stats(self, *, tests: Iterable[str] | None) -> int:
        """Run tests and collect statistics."""
        raise NotImplementedError()

    @abstractmethod
    def run_forced_fail(self) -> int:
        """Run tests in forced fail mode."""
        raise NotImplementedError()

    def prepare_main_test_run(self) -> None:  # noqa: B027
        """Prepare for the main test run (optional hook)."""

    @abstractmethod
    def run_tests(self, *, mutant_name: str | None, tests: Iterable[str] | None) -> int:
        """Run tests for a specific mutant."""
        raise NotImplementedError()

    @abstractmethod
    def list_all_tests(self) -> ListAllTestsResult:
        """List all tests in the test suite."""
        raise NotImplementedError()

    def get_init_args(self) -> dict[str, object]:
        """Return the arguments needed to reconstruct this runner in a subprocess.

        For subprocess workers to instantiate the same runner, they need to know
        what arguments to pass. The default implementation returns an empty dict,
        which works for runners that read config from mutmut.config in __init__.
        """
        return {}

    def warm_up(self) -> None:
        """Pre-import expensive modules so forked children inherit them.

        Called by HotForkRunner after creating the test runner in the orchestrator.
        Importing pytest and running test collection here means grandchildren
        fork with pytest already in memory, saving ~4 seconds per mutant.

        Default implementation is a no-op for runners that don't need it.
        """
        return


class PytestRunner(TestRunner):
    """Test runner that uses pytest."""

    def __init__(self) -> None:
        self._pytest_add_cli_args: list[str] = config().pytest_add_cli_args
        self._pytest_add_cli_args_test_selection: list[str] = config().pytest_add_cli_args_test_selection

        # tests_dir is a special case of a test selection option,
        # so also use pytest_add_cli_args_test_selection for the implementation
        self._pytest_add_cli_args_test_selection += config().tests_dir

    def warm_up(self) -> None:
        """Pre-load modules in current execution context so forked children inherit them.

        Behavior is controlled by hot_fork_warmup config:

        1. hot_fork_warmup = "collect" (default):
           Runs pytest --collect-only which loads conftest.py, plugins, and
           discovers all tests. Provides ~5x speedup. Best for most projects.

        2. hot_fork_warmup = "import":
           Imports modules listed in preload_modules_file. Useful when test
           collection has side effects that shouldn't be shared.

        3. hot_fork_warmup = "none":
           Just import pytest without collection. Minimal warmup.
        """

        warmup = config().hot_fork_warmup

        if warmup == HotForkWarmup.COLLECT:
            # Run pytest --collect-only to pre-load test infrastructure
            import pytest

            with change_cwd("mutants"):
                pytest.main(
                    ["--collect-only", "-q", "--rootdir=."] + self._pytest_add_cli_args_test_selection,
                )
        elif warmup == HotForkWarmup.IMPORT:
            # Import modules from preload file
            preload_file = config().preload_modules_file
            if preload_file:
                import importlib

                with open(preload_file) as f:
                    for line in f:
                        module_name = line.strip()
                        if module_name and not module_name.startswith("#"):
                            try:
                                importlib.import_module(module_name)
                            except ImportError:
                                pass  # Best effort
        else:
            # warmup == HotForkWarmup.NONE - just import pytest (required to run tests
            # in a forked process)
            import pytest  # noqa: F401

    # noinspection PyMethodMayBeStatic
    def execute_pytest(self, params: list[str], **kwargs: object) -> int:
        """Execute pytest with the given parameters."""
        import pytest

        params = ["--rootdir=.", "--tb=native"] + params + self._pytest_add_cli_args
        if config().debug:
            params = ["-vv"] + params
            print("python -m pytest ", " ".join([f'"{param}"' for param in params]))
        exit_code = int(pytest.main(params, **kwargs))  # type: ignore[arg-type]
        if config().debug:
            print("    exit code", exit_code)
        if exit_code == 4:
            raise BadTestExecutionCommandsException(params)
        return exit_code

    def run_stats(self, *, tests: Iterable[str] | None) -> int:
        """Run tests and collect statistics."""

        class StatsCollector:
            # noinspection PyMethodMayBeStatic
            def pytest_runtest_logstart(self, nodeid: str, location: object) -> None:
                state().duration_by_test[nodeid] = 0

            # noinspection PyMethodMayBeStatic
            def pytest_runtest_teardown(self, item: object, nextitem: object) -> None:
                unused(nextitem)
                for function in state()._stats:
                    state().tests_by_mangled_function_name[function].add(strip_prefix(item._nodeid, prefix="mutants/"))  # type: ignore[attr-defined]
                state()._stats.clear()

            # noinspection PyMethodMayBeStatic
            def pytest_runtest_makereport(self, item: object, call: object) -> None:
                state().duration_by_test[item.nodeid] += call.duration  # type: ignore[attr-defined]

        stats_collector = StatsCollector()

        pytest_args = ["-x", "-q"]
        if tests:
            pytest_args += list(tests)
        else:
            pytest_args += self._pytest_add_cli_args_test_selection
        with change_cwd("mutants"):
            return int(self.execute_pytest(pytest_args, plugins=[stats_collector]))

    def run_tests(self, *, mutant_name: str | None, tests: Iterable[str] | None) -> int:
        """Run tests for a specific mutant."""
        pytest_args = ["-x", "-q", "-p", "no:randomly", "-p", "no:random-order"]
        if tests:
            pytest_args += list(tests)
        else:
            pytest_args += self._pytest_add_cli_args_test_selection
        with change_cwd("mutants"):
            return int(self.execute_pytest(pytest_args))

    def run_forced_fail(self) -> int:
        """Run tests in forced fail mode."""
        pytest_args = ["-x", "-q"] + self._pytest_add_cli_args_test_selection
        with change_cwd("mutants"):
            return int(self.execute_pytest(pytest_args))

    def list_all_tests(self) -> ListAllTestsResult:
        """List all tests in the test suite."""

        class TestsCollector:
            def __init__(self) -> None:
                self.collected_nodeids: set[str] = set()
                self.deselected_nodeids: set[str] = set()

            def pytest_collection_modifyitems(self, items: list[object]) -> None:
                self.collected_nodeids |= {item.nodeid for item in items}  # type: ignore[attr-defined]

            def pytest_deselected(self, items: list[object]) -> None:
                self.deselected_nodeids |= {item.nodeid for item in items}  # type: ignore[attr-defined]

        collector = TestsCollector()

        pytest_args = [
            "-x",
            "-q",
            "--collect-only",
        ] + self._pytest_add_cli_args_test_selection

        with change_cwd("mutants"):
            exit_code = int(self.execute_pytest(pytest_args, plugins=[collector]))
            if exit_code != 0:
                raise CollectTestsFailedException()

        selected_nodeids = collector.collected_nodeids - collector.deselected_nodeids
        return ListAllTestsResult(ids=selected_nodeids)


class HammettRunner(TestRunner):
    """Test runner that uses hammett."""

    def __init__(self) -> None:
        self.hammett_kwargs: dict[str, object] | None = None

    def run_stats(self, *, tests: Iterable[str] | None) -> int:
        """Run tests and collect statistics."""
        import hammett

        print("Running hammett stats...")

        def post_test_callback(_name: str, **_: object) -> None:
            for function in state()._stats:
                state().tests_by_mangled_function_name[function].add(_name)
            state()._stats.clear()

        return int(
            hammett.main(
                quiet=True,
                fail_fast=True,
                disable_assert_analyze=True,
                post_test_callback=post_test_callback,
                use_cache=False,
                insert_cwd=False,
            )
        )

    def run_forced_fail(self) -> int:
        """Run tests in forced fail mode."""
        import hammett

        return int(
            hammett.main(
                quiet=True,
                fail_fast=True,
                disable_assert_analyze=True,
                use_cache=False,
                insert_cwd=False,
            )
        )

    def prepare_main_test_run(self) -> None:
        """Prepare for the main test run."""
        import hammett

        self.hammett_kwargs = hammett.main_setup(
            quiet=True,
            fail_fast=True,
            disable_assert_analyze=True,
            use_cache=False,
            insert_cwd=False,
        )

    def run_tests(self, *, mutant_name: str | None, tests: Iterable[str] | None) -> int:
        """Run tests for a specific mutant."""
        import hammett

        hammett.Config.workerinput = {"workerinput": f"_{mutant_name}"}
        return int(hammett.main_run_tests(**self.hammett_kwargs, tests=tests))

    def list_all_tests(self) -> ListAllTestsResult:
        """List all tests in the test suite."""
        raise NotImplementedError()

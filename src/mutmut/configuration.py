from __future__ import annotations

import fnmatch
import os
import sys
from collections.abc import Callable
from configparser import ConfigParser
from configparser import NoOptionError
from configparser import NoSectionError
from dataclasses import dataclass
from enum import Enum
from os.path import isdir
from os.path import isfile
from pathlib import Path
from typing import Any


class ProcessIsolation(str, Enum):
    """Valid values for process_isolation config.

    Using str, Enum allows direct string comparison while providing
    validation and IDE support.
    """

    FORK = "fork"  # Default: current behavior
    HOT_FORK = "hot-fork"  # Fork-safe for gevent/grpc


class HotForkWarmup(str, Enum):
    """Warmup strategies for hot-fork orchestrator.

    Controls what the orchestrator does before forking grandchildren:
    - COLLECT: Run pytest --collect-only to pre-load test infrastructure (DEFAULT)
    - IMPORT: Import modules from a file (useful when test collection has side effects)
    - NONE: Just import pytest, no test collection
    """

    COLLECT = "collect"  # Default: ~5.5x speedup from pre-loaded tests
    IMPORT = "import"
    NONE = "none"


def _config_reader() -> Callable[[str, Any], Any]:
    path = Path("pyproject.toml")
    if path.exists():
        if sys.version_info >= (3, 11):
            from tomllib import loads
        else:
            # noinspection PyPackageRequirements
            from toml import loads
        data = loads(path.read_text("utf-8"))

        try:
            config = data["tool"]["mutmut"]
        except KeyError:
            pass
        else:

            def toml_conf(key: str, default: Any) -> Any:
                try:
                    result = config[key]
                except KeyError:
                    return default
                return result

            return toml_conf

    config_parser = ConfigParser()
    config_parser.read("setup.cfg")

    def setup_cfg_conf(key: str, default: Any) -> Any:
        try:
            result = config_parser.get("mutmut", key)
        except (NoOptionError, NoSectionError):
            return default
        if isinstance(default, list):
            if "\n" in result:
                return [x for x in result.split("\n") if x]
            else:
                return [result]
        elif isinstance(default, bool):
            return result.lower() in ("1", "t", "true")
        elif isinstance(default, int):
            return int(result)
        return result

    return setup_cfg_conf


def _guess_paths_to_mutate() -> list[str]:
    """Guess the path to source code to mutate

    :rtype: str
    """
    this_dir = os.getcwd().split(os.sep)[-1]
    if isdir("lib"):
        return ["lib"]
    elif isdir("src"):
        return ["src"]
    elif isdir(this_dir):
        return [this_dir]
    elif isdir(this_dir.replace("-", "_")):
        return [this_dir.replace("-", "_")]
    elif isdir(this_dir.replace(" ", "_")):
        return [this_dir.replace(" ", "_")]
    elif isdir(this_dir.replace("-", "")):
        return [this_dir.replace("-", "")]
    elif isdir(this_dir.replace(" ", "")):
        return [this_dir.replace(" ", "")]
    if isfile(this_dir + ".py"):
        return [this_dir + ".py"]
    raise FileNotFoundError(
        "Could not figure out where the code to mutate is. "
        'Please specify it by adding "paths_to_mutate=code_dir" in setup.cfg to the [mutmut] section.'
    )


def _load_config() -> Config:
    s = _config_reader()

    # Validate process_isolation (default: fork - preserves current behavior)
    isolation_str = s("process_isolation", "fork")
    try:
        process_isolation = ProcessIsolation(isolation_str)
    except ValueError:
        valid = [e.value for e in ProcessIsolation]
        raise ValueError(f"Invalid process_isolation value: {isolation_str!r}. Expected one of: {valid}") from None

    # Validate hot_fork_warmup (default: collect)
    warmup_str = s("hot_fork_warmup", "collect")
    try:
        hot_fork_warmup = HotForkWarmup(warmup_str)
    except ValueError:
        valid = [e.value for e in HotForkWarmup]
        raise ValueError(f"Invalid hot_fork_warmup value: {warmup_str!r}. Expected one of: {valid}") from None

    return Config(
        do_not_mutate=s("do_not_mutate", []),
        also_copy=[Path(y) for y in s("also_copy", [])]
        + [
            Path("tests/"),
            Path("test/"),
            Path("setup.cfg"),
            Path("pyproject.toml"),
        ]
        + list(Path(".").glob("test*.py")),
        max_stack_depth=s("max_stack_depth", -1),
        debug=s("debug", False),
        mutate_only_covered_lines=s("mutate_only_covered_lines", False),
        paths_to_mutate=[Path(y) for y in s("paths_to_mutate", [])] or [Path(p) for p in _guess_paths_to_mutate()],
        tests_dir=s("tests_dir", []),
        pytest_add_cli_args=s("pytest_add_cli_args", []),
        pytest_add_cli_args_test_selection=s("pytest_add_cli_args_test_selection", []),
        type_check_command=s("type_check_command", []),
        track_dependencies=s("track_dependencies", True),
        dependency_tracking_depth=s("dependency_tracking_depth", None),
        process_isolation=process_isolation,
        max_orchestrator_restarts=s("max_orchestrator_restarts", 3),
        hot_fork_warmup=hot_fork_warmup,
        preload_modules_file=s("preload_modules_file", None),
    )


@dataclass
class Config:
    also_copy: list[Path]
    do_not_mutate: list[str]
    max_stack_depth: int
    debug: bool
    paths_to_mutate: list[Path]
    pytest_add_cli_args: list[str]
    pytest_add_cli_args_test_selection: list[str]
    tests_dir: list[str]
    mutate_only_covered_lines: bool
    type_check_command: list[str]
    track_dependencies: bool
    dependency_tracking_depth: int | None
    process_isolation: ProcessIsolation  # Default: FORK (preserves current behavior)
    max_orchestrator_restarts: int  # Default: 3
    hot_fork_warmup: HotForkWarmup  # Default: COLLECT
    preload_modules_file: str | None  # Default: None (for IMPORT warmup)

    def should_ignore_for_mutation(self, path: Path | str) -> bool:
        path_str = str(path)
        if not path_str.endswith(".py"):
            return True
        for p in self.do_not_mutate:
            if fnmatch.fnmatch(path_str, p):
                return True
        return False


_config: Config | None = None


def config() -> Config:
    """Get the global configuration singleton, creating it if needed."""
    global _config
    if _config is None:
        _config = _load_config()
    return _config


def reset_config() -> None:
    """Reset the global configuration. Primarily used for testing."""
    global _config
    _config = None

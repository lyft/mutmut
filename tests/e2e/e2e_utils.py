import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from mutmut.__main__ import _run
from mutmut.configuration import config
from mutmut.models.source_file_mutation_data import SourceFileMutationData
from mutmut.utils.file_utils import walk_source_files
from tests.conftest import reset_singletons


@contextmanager
def change_cwd(path: Path):
    old_cwd = Path(Path.cwd()).resolve()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def read_all_stats_for_project(project_path: Path, include_hashes: bool = False) -> dict[str, Any]:
    """Create a single dict from all mutant results in *.meta files.

    Args:
        project_path: Path to the project
        include_hashes: If True, include function hashes in output for stability testing

    Returns:
        Dict with exit codes and optionally function hashes
    """
    with change_cwd(project_path):
        reset_singletons()

        stats: dict[str, Any] = {}
        for p in walk_source_files():
            if config().should_ignore_for_mutation(p):
                continue
            data = SourceFileMutationData(path=p)
            data.load()
            meta_key = str(data.meta_path)
            stats[meta_key] = {"exit_codes": data.exit_code_by_key}
            if include_hashes:
                stats[meta_key]["function_hashes"] = data.hash_by_function_name

        return stats


def read_json_file(path: Path):
    with open(path) as file:
        return json.load(file)


def write_json_file(path: Path, data: Any):
    with open(path, "w") as file:
        json.dump(data, file, indent=2, sort_keys=True)
        file.write("\n")  # ensure newline at end of file for POSIX compliance


def asserts_results_did_not_change(project: str, include_hashes: bool = False):
    """Runs mutmut on this project and verifies that the results stay the same for all mutations.

    Args:
        project: Name of the project in e2e_projects/
        include_hashes: If True, also verify function hashes are stable
    """
    project_path = Path("..").parent / "e2e_projects" / project

    mutants_path = project_path / "mutants"
    shutil.rmtree(mutants_path, ignore_errors=True)

    # mutmut run
    with change_cwd(project_path):
        reset_singletons()
        _run([], None)

    results = read_all_stats_for_project(project_path, include_hashes=include_hashes)

    snapshot_path = Path("tests") / "e2e" / "snapshots" / (project + ".json")

    if snapshot_path.exists():
        # compare results against previous snapshot
        previous_snapshot = read_json_file(snapshot_path)

        # Handle backwards compatibility: old snapshots have flat exit_codes directly
        if previous_snapshot and not include_hashes:
            first_value = next(iter(previous_snapshot.values()), None)
            if isinstance(first_value, dict) and "exit_codes" not in first_value:
                # Old format: convert results to old format for comparison
                results = {k: v["exit_codes"] for k, v in results.items()}

        err_msg = f"Mutmut results changed for the E2E project '{project}'. If this change was on purpose, delete {snapshot_path} and rerun the tests."
        assert results == previous_snapshot, err_msg
    else:
        # create the first snapshot
        write_json_file(snapshot_path, results)


def run_mutmut_on_project(project: str) -> dict:
    """Runs mutmut on this project and returns the results (for inline snapshot tests)."""
    project_path = Path("..").parent / "e2e_projects" / project

    mutants_path = project_path / "mutants"
    shutil.rmtree(mutants_path, ignore_errors=True)

    # mutmut run
    with change_cwd(project_path):
        reset_singletons()
        _run([], None)

    return read_all_stats_for_project(project_path)

"""
Statistics collection and reporting for mutmut.

This module contains the Stat dataclass and functions for collecting
and printing mutation testing statistics.
"""

from collections import defaultdict
from dataclasses import dataclass

from mutmut.models.source_file_mutation_data import SourceFileMutationData
from mutmut.ui.terminal import print_status

status_by_exit_code = defaultdict(
    lambda: "suspicious",
    {
        1: "killed",
        3: "killed",  # internal error in pytest means a kill
        -24: "killed",
        0: "survived",
        5: "no tests",
        2: "check was interrupted by user",
        None: "not checked",
        33: "no tests",
        34: "skipped",
        35: "suspicious",
        36: "timeout",
        37: "caught by type check",
        -24: "timeout",  # SIGXCPU
        24: "timeout",  # SIGXCPU
        152: "timeout",  # SIGXCPU
        255: "timeout",
        -11: "segfault",
        -9: "segfault",
    },
)

emoji_by_status = {
    "survived": "🙁",
    "no tests": "🫥",
    "timeout": "⏰",
    "suspicious": "🤔",
    "skipped": "🔇",
    "caught by type check": "🧙",
    "check was interrupted by user": "🛑",
    "not checked": "?",
    "killed": "🎉",
    "segfault": "💥",
}

exit_code_to_emoji = {exit_code: emoji_by_status[status] for exit_code, status in status_by_exit_code.items()}


@dataclass
class Stat:
    """Statistics for mutation testing results."""

    not_checked: int
    killed: int
    survived: int
    total: int
    no_tests: int
    skipped: int
    suspicious: int
    timeout: int
    check_was_interrupted_by_user: int
    segfault: int
    caught_by_type_check: int


def collect_stat(m: SourceFileMutationData) -> Stat:
    """Collect statistics from a SourceFileMutationData object.

    Args:
        m: The mutation data to collect stats from.

    Returns:
        A Stat object with the collected statistics.
    """
    r = {k.replace(" ", "_"): 0 for k in status_by_exit_code.values()}
    for val in m.exit_code_by_key.values():
        # noinspection PyTypeChecker
        r[status_by_exit_code[val].replace(" ", "_")] += 1
    return Stat(
        **r,
        total=sum(r.values()),
    )


def calculate_summary_stats(
    source_file_mutation_data_by_path: dict[str, SourceFileMutationData],
) -> Stat:
    """Calculate summary statistics across all source files.

    Args:
        source_file_mutation_data_by_path: Mapping from paths to mutation data.

    Returns:
        A Stat object with the aggregated statistics.
    """
    stats = [collect_stat(x) for x in source_file_mutation_data_by_path.values()]
    return Stat(
        not_checked=sum(x.not_checked for x in stats),
        killed=sum(x.killed for x in stats),
        survived=sum(x.survived for x in stats),
        total=sum(x.total for x in stats),
        no_tests=sum(x.no_tests for x in stats),
        skipped=sum(x.skipped for x in stats),
        suspicious=sum(x.suspicious for x in stats),
        timeout=sum(x.timeout for x in stats),
        check_was_interrupted_by_user=sum(x.check_was_interrupted_by_user for x in stats),
        segfault=sum(x.segfault for x in stats),
        caught_by_type_check=sum(x.caught_by_type_check for x in stats),
    )


def print_stats(
    source_file_mutation_data_by_path: dict[str, SourceFileMutationData],
    force_output: bool = False,
) -> None:
    """Print mutation testing statistics.

    Args:
        source_file_mutation_data_by_path: Mapping from paths to mutation data.
        force_output: Whether to force output even if rate-limited.
    """
    s = calculate_summary_stats(source_file_mutation_data_by_path)
    print_status(
        f"{(s.total - s.not_checked)}/{s.total}  🎉 {s.killed} 🫥 {s.no_tests}  ⏰ {s.timeout}  🤔 {s.suspicious}  🙁 {s.survived}  🔇 {s.skipped}  🧙 {s.caught_by_type_check}",
        force_output=force_output,
    )

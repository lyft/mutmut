from inline_snapshot import snapshot

from tests.e2e.e2e_utils import run_mutmut_on_project


def test_hot_fork_gevent_result_snapshot():
    assert run_mutmut_on_project("hot_fork_gevent") == snapshot(
        {"mutants/src/app/__init__.py.meta": {"exit_codes": {"app.x_add__mutmut_1": 1, "app.x_subtract__mutmut_1": 1}}}
    )

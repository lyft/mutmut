from inline_snapshot import snapshot

from tests.e2e.e2e_utils import run_mutmut_on_project


def test_hot_fork_basic_result_snapshot():
    assert run_mutmut_on_project("hot_fork_basic") == snapshot(
        {
            "mutants/src/calc/__init__.py.meta": {
                "exit_codes": {
                    "calc.x_divide__mutmut_1": 1,
                    "calc.x_divide__mutmut_2": 1,
                    "calc.x_divide__mutmut_3": 1,
                    "calc.x_divide__mutmut_4": 1,
                }
            }
        }
    )

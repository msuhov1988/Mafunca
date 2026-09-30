import unittest


from test_curry import TestCurry, TestAsyncCurry
from test_result import TestResult
from test_maybe import TestMaybe
from test_result_transformer import TestResultMaybeT
from test_maybe_transformer import TestMaybeResultT
from test_effect import TestEffectSync
from test_effect_generator import TestEffGenBased
from test_effect_result_generator import TestEffResultGenBased
from test_aff import TestEffectAsync
from test_aff_generator import TestAffGenBased
from test_aff_result_generator import TestAffResultGenBased


def add_tests_for_class(suite: unittest.TestSuite, test_class: type[unittest.TestCase]):    
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))


if __name__ == "__main__":
    test_suite = unittest.TestSuite()
    tests: list[type[unittest.TestCase]] = [
        TestCurry,
        TestAsyncCurry,
        TestResult,
        TestMaybe,
        TestResultMaybeT,
        TestMaybeResultT,
        TestEffectSync,
        TestEffectAsync,
        TestEffGenBased,
        TestEffResultGenBased,
        TestAffGenBased,
        TestAffResultGenBased,
    ]
    for test_cls in tests:
        add_tests_for_class(test_suite, test_cls)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)

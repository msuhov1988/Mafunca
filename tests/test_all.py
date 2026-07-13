import unittest
import sys


from test_curry import TestCurry, TestAsyncCurry
from test_result import TestResult
from test_maybe import TestMaybe
from test_result_transformer import TestResultMaybeT
from test_maybe_transformer import TestMaybeResultT
from test_effect_sync import TestEffectSync
from test_effect_async import TestEffectAsync


def add_tests_for_class(suite, test_class):
    if sys.version_info < (3, 13):
        suite.addTest(unittest.makeSuite(test_class))
    else:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))


if __name__ == "__main__":
    test_suite = unittest.TestSuite()
    tests = [
        TestCurry,
        TestAsyncCurry,
        TestResult,
        TestMaybe,
        TestResultMaybeT,
        TestMaybeResultT,
        TestEffectSync,
        TestEffectAsync,
    ]
    for test_cls in tests:
        add_tests_for_class(test_suite, test_cls)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)

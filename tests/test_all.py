import unittest
import sys


from test_triple_and_curry import TestTripleAndCurry, TestAsyncCurry
from test_effsync import TestEffSync
from test_eff import TestEff


def add_tests_for_class(suite, test_class):
    if sys.version_info < (3, 13):
        suite.addTest(unittest.makeSuite(test_class))
    else:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))


if __name__ == "__main__":
    test_suite = unittest.TestSuite()
    for test_cls in [TestTripleAndCurry, TestAsyncCurry, TestEffSync, TestEff]:
        add_tests_for_class(test_suite, test_cls)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)

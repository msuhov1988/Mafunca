from typing import Callable
import unittest

from mafunca.result import Success, Fail, success, fail, is_success, is_fail, from_try
from mafunca.result_direct import fmap, fmap_error, bind, fold, get_or_else, ap
from mafunca.result_lift import lift, lift2, lift3, lift4

from mafunca.flow import flow
import mafunca.result_flow as rf

from mafunca.common.exceptions import MonadError


class TestResult(unittest.TestCase):
    def test_introspection(self):
        right1 = Success(1)
        self.assertTrue(is_success(right1))
        self.assertFalse(is_fail(right1))

        right2 = success(1)
        self.assertTrue(is_success(right2))
        self.assertFalse(is_fail(right2))

        err1 = Fail(1)
        self.assertFalse(is_success(err1))
        self.assertTrue(is_fail(err1))

        err2 = fail(1)  # noqa
        self.assertFalse(is_success(err2))
        self.assertTrue(is_fail(err2))

    def test_ok_chains(self):
        
        res1 = success(2)
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: Success(x + 1))
        res1 = fold(res1, on_success=lambda x: x ** 2, on_fail=lambda _: 0)
        self.assertEqual(res1, 16)

        res2 = flow(
            success(2),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: Success(x + 1)),
            rf.fold(on_success=lambda x: x ** 2, on_fail=lambda _: 0)
        )
        self.assertEqual(res2, 16)

        res3 = success(1)
        res3 = fmap(res3, lambda x: x + 1)
        res3 = bind(res3, lambda x: Success(x + 1))
        res3 = get_or_else(res3, 100)
        self.assertEqual(res3, 3)

        res4 = flow(
            success(1),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: Success(x + 1)),
            rf.get_or_else(100)
        )        
        self.assertEqual(res4, 3)

        res5 = success(1)
        res5 = fmap(res5, lambda x: x + 1)
        res5 = fmap(res5, lambda x: Success(x + 1))
        res5 = fold(res5, on_success=lambda v: v, on_fail=lambda e: e)
        self.assertIsInstance(res5, Success)
        self.assertEqual(get_or_else(res5, 100), 3)

        res6 = flow(
            success(1),
            rf.fmap(lambda x: x + 1),
            rf.fmap(lambda x: success(x + 1)),
            rf.fold(on_success=lambda v: v, on_fail=lambda e: e),
        )
        self.assertIsInstance(res6, Success)
        self.assertEqual(get_or_else(res6, 100), 3)

        res7 = success(2)
        res7 = bind(res7, lambda _: fail(0))
        res7 = fmap(res7, lambda x: x + 1)
        self.assertIsInstance(res7, Fail)
        res7 = fold(res7, on_success=lambda v: v, on_fail=lambda e: e)
        self.assertTrue(res7 == 0)

        res8 = flow(
            success(2),
            rf.bind(lambda _: fail(0)),
            rf.fmap(lambda x: x + 1),
            rf.fold(on_success=lambda v: v, on_fail=lambda e: e)
        )
        self.assertTrue(res8 == 0)

        res9 = success(2)
        res9 = fmap_error(res9, lambda _: 100)
        res9 = fold(res9, on_success=lambda v: v, on_fail=lambda e: e)
        self.assertEqual(res9, 2)

        res10 = flow(
            success(2),
            rf.fmap_error(lambda _: 100),
            rf.fold(on_success=lambda v: v, on_fail=lambda e: e)
        )
        self.assertEqual(res10, 2)

    def test_err_chains(self):
        res1 = fail(1)
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: success(x + 1))
        self.assertIsInstance(res1, Fail)
        self.assertEqual(get_or_else(res1, 100), 100)

        res2 = flow(
            fail(1),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: Success(x + 1))
        )
        self.assertIsInstance(res2, Fail)
        self.assertEqual(get_or_else(res2, 100), 100)

        res3 = fail(1)
        res3 = fmap(res3, lambda x: x + 1)
        res3 = bind(res3, lambda x: success(x + 1))
        res3 = get_or_else(res3, 100)
        self.assertEqual(res3, 100)

        res4 = flow(
            fail(1),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: Success(x + 1)),
            rf.get_or_else(100),
        )        
        self.assertEqual(res4, 100)

        res5 = fail("Some error")
        res5 = fmap(res5, lambda x: x + 1)
        res5 = bind(res5, lambda x: success(x + 1))
        res5 = fold(res5, on_success=lambda x: [str(x ** 2)], on_fail=lambda x: [x])
        self.assertEqual(res5, ["Some error"])

        res6 = flow(
            fail("Some error"),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: Success(x + 1)),
            rf.fold(on_success=lambda x: [str(x ** 2)], on_fail=lambda x: [x])
        )
        self.assertEqual(res6, ["Some error"])

        res7 = fail("Some error")
        res7 = fmap_error(res7, lambda e: [e])
        res7 = fold(res7, on_success=lambda _: [], on_fail=lambda e: e)
        self.assertEqual(res7, ["Some error"])

        res8 = flow(
            fail("Some error"),
            rf.fmap_error(lambda e: [e]),
            rf.bind(lambda x: Success(x + 1)),
            rf.fold(on_success=lambda _: [], on_fail=lambda e: e)
        )
        self.assertEqual(res8, ["Some error"])

    def test_from_try(self):
        @from_try
        def test_from_try(a: int):
            if a < 0:
                raise TypeError("test")
            return a ** 2

        res = flow(test_from_try(-1), rf.fmap(lambda x: x + 1), rf.bind(lambda x: Success(x)))
        self.assertTrue(is_fail(res))
        self.assertTrue(fold(res, on_success=lambda _: False, on_fail=lambda e: isinstance(e, TypeError)))

        res = flow(test_from_try(10), rf.fmap(lambda x: x + 1), rf.bind(lambda x: Success(x + 1)))
        self.assertTrue(is_success(res))
        self.assertEqual(fold(res, on_success=lambda x: x + 1, on_fail=lambda _: 0), 103)

    def test_from_try_monad_error(self):
        @from_try
        def raiser(a: int):
            _ = a + 1
            raise MonadError("test", "test", "test")

        with self.assertRaises(MonadError):
            raiser(1)

    def test_ap(self):
        def one(a: int):
            return [a]

        res = get_or_else(ap(success(10), success(one)), [0])
        self.assertEqual(res, [10])

        res = ap(Fail(10), success(one))
        self.assertTrue(is_fail(res))
        self.assertEqual(get_or_else(res, 0), 0)

        res = ap(fail(0), success(lambda _: 10))
        self.assertTrue(is_fail(res))
        self.assertEqual(get_or_else(res, 100), 100)

    def test_ap_flow(self):
        def one(a: int) -> Callable[[int], Callable[[int], list[int]]]:

            def one_inner(b: int) -> Callable[[int], list[int]]:

                def one_inner_inner(c: int) -> list[int]:
                    return [a, b, c]

                return one_inner_inner

            return one_inner

        res = flow(success(one), rf.ap(success(1)), rf.ap(success(2)), rf.ap(success(3)))
        res = get_or_else(res, [])
        self.assertEqual(res, [1, 2, 3])

        res = flow(success(one), rf.ap(success(1)), rf.ap(success(2)), rf.ap(fail(3)))
        res = get_or_else(res, [])
        self.assertEqual(res, [])

        res = flow(success(one), rf.ap(success(1)), rf.ap(success(2)), rf.ap(Fail(3)))
        res = get_or_else(res, [])
        self.assertEqual(res, [])        
        

    def test_lift2(self):
        def two(a: int, b: int):
            return [a, b]

        res = get_or_else(lift2(two, success(1), success(2)), [])
        self.assertEqual(res, [1, 2])
        res = lift2(two, Success(1), Fail(2))
        self.assertTrue(is_fail(res))
        self.assertEqual(get_or_else(res, 100), 100)
        res = get_or_else(lift2(two, Fail(1), Success(2)), [])
        self.assertEqual(res, [])

    def test_lift3(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        res = get_or_else(lift3(three, success(1), success(2), success(3)), [0])
        self.assertEqual(res, [1, 2, 3])
        res = lift3(three, success(1), fail(2), fail(3))
        self.assertTrue(is_fail(res))
        self.assertEqual(get_or_else(res, 100), 100)
        res = get_or_else(lift3(three, Success(1), Fail(2), Success(3)), [])
        self.assertEqual(res, [])

    def test_lift4(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]

        res = get_or_else(lift4(four, success(1), success(2), success(3), success(4)), [])
        self.assertEqual(res, [1, 2, 3, 4])
        res = lift4(four, Success(1), Fail(None), Success(3), Success(4))
        self.assertTrue(is_fail(res))        
        res = get_or_else(lift4(four, Success(1), Fail(None), Success(3), Success(4)), [])
        self.assertEqual(res, [])

    def test_lift(self):
        def many(a: int, b: int, c: int, d: int, e: int):
            return [a, b, c, d, e]

        res = lift(many, Success(1), Success(2), Success(3), Success(4), Success(5))
        res = fold(res, on_success=lambda v: v, on_fail=lambda _: [])
        self.assertEqual(res, [1, 2, 3, 4, 5])
        res = lift(many, Success(1), Fail(2), Success(3), Success(4), Success(5))
        self.assertTrue(is_fail(res))        
        res = get_or_else(lift(many, Success(1), Fail(2), Success(3), Success(4), Success(5)), [])
        self.assertEqual(res, [])        


if __name__ == "__main__":
    unittest.main()

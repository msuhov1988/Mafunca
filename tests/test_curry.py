import unittest
from inspect import iscoroutine
import asyncio

from mafunca.common.exceptions import CurryBadArguments
from mafunca.curry import curry2, curry3, curry4, curry


class TestCurry(unittest.TestCase):

    def test_curry2(self):
        @curry2
        def test(a: int, b: int) -> int:
            return a + b

        self.assertTrue(callable(test(1)))
        self.assertEqual(test(1)(2), 3)

    def test_curry3(self):
        def test(a: int, b: int, c: int) -> int:
            return a + b + c

        test_result = curry3(test)

        self.assertTrue(callable(test_result(1)))
        self.assertTrue(callable(test_result(1)(2)))
        self.assertEqual(test_result(1)(2)(3), 6)

    def test_curry4(self):
        def test(a: int, b: int, c: int, d: int) -> int:
            return a + b + c + d

        test_result = curry4(test)

        self.assertTrue(callable(test_result(1)))
        self.assertTrue(callable(test_result(1)(2)))
        self.assertTrue(callable(test_result(1)(2)(3)))
        self.assertEqual(test_result(1)(2)(3)(4), 10)

    def test_curry_basic(self):
        @curry
        def for_curry(a: int, b: int, c: int = 0, d: int = 0) -> list[int]:
            return [a, b, c, d]

        self.assertEqual(for_curry(1)(2)(3)(4), [1, 2, 3, 4])
        self.assertEqual(for_curry(1)(2)(), [1, 2, 0, 0])
        self.assertEqual(for_curry()(b=2, a=1), [1, 2, 0, 0])
        self.assertEqual(for_curry(1, 2)(c=3)(), [1, 2, 3, 0])
        self.assertEqual(for_curry(1, 2)(d=3)(), [1, 2, 0, 3])

    def test_curry_variant_args(self):
        @curry
        def for_curry(a: int, b: int, *args, **kwargs) -> list:
            return [a, b, args, kwargs]

        res = for_curry(1, b=2)
        self.assertTrue(callable(for_curry))
        res = res(0, 0)
        self.assertTrue(callable(for_curry))
        res = res(another=10)
        self.assertEqual(res, [1, 2, (0, 0), {'another': 10}])

    def test_curry_repeatable_currying(self):
        @curry
        @curry
        def for_curry(a: int, b: int, *args, **kwargs) -> list:
            return [a, b, args, kwargs]

        res = for_curry(1, b=2)
        self.assertTrue(callable(for_curry))
        res = res(0, 0)
        self.assertTrue(callable(for_curry))
        res = res(another=10)
        self.assertEqual(res, [1, 2, (0, 0), {'another': 10}])

    def test_curry_signature_preserved(self):
        @curry
        def for_curry_three(a: int, *, b: int) -> int:
            return a + b

        with self.assertRaises(CurryBadArguments):
            for_curry_three(1)(2)  # signature of the original function are preserved - the second arg is only named
        self.assertEqual(for_curry_three(1)(b=2), 3)

    def test_curry_fail_fast(self):
        @curry
        def for_curry(a, b):
            return a + b

        with self.assertRaises(CurryBadArguments):
            for_curry(c=1)
        self.assertEqual(for_curry(1)(b=2), 3)


class TestAsyncCurry(unittest.IsolatedAsyncioTestCase):
    async def test_async_curry_basic(self):
        @curry
        async def for_curry(a: int, b: int, c: int = 0, d: int = 0) -> list[int]:
            await asyncio.sleep(0)
            return [a, b, c, d]

        res = for_curry(1)
        res = res(2)
        res = res(3)
        res = await res(4)
        self.assertEqual(res, [1, 2, 3, 4])

        res = for_curry()
        res = await res(b=2, a=1)
        self.assertEqual(res, [1, 2, 0, 0])

        res = for_curry(1, 2, 3, 4)
        self.assertEqual(iscoroutine(res), True)

        res = await res
        self.assertEqual(res, [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()

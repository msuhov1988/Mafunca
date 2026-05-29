import unittest
from inspect import iscoroutine
import asyncio

from mafunca.common.exceptions import CurryBadArguments
from mafunca.curry import curry
from mafunca.specials import impure, is_impure


class TestCurry(unittest.TestCase):

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
        res = for_curry(b=2)(a=1)
        self.assertEqual(res.run_for_var(), [1, 2, (), {}])

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

    def test_is_impure(self):
        @impure
        def test(a, b):
            return a, b

        curried = curry(test)
        self.assertEqual(is_impure(curried), True)

        curried = curried(3)
        self.assertEqual(is_impure(curried), True)


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

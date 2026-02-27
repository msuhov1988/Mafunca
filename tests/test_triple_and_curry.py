import unittest
import asyncio

from mafunca.triple import Right, Left, Nothing, TUtils, impure
from mafunca.common.exceptions import MonadError, CurryBadArguments
from mafunca.curry import curry, async_curry


class TestTripleAndCurry(unittest.TestCase):
    def test_introspection_right_left_nothing(self):
        right = Right(1)
        self.assertTrue(right.is_right)
        self.assertFalse(right.is_nothing)

        from_unit = TUtils.unit(1)
        self.assertTrue(from_unit.is_right)
        self.assertFalse(from_unit.is_nothing)

        left = Left(1)
        self.assertFalse(left.is_right)
        self.assertFalse(left.is_nothing)

        nothing = Nothing()
        self.assertFalse(nothing.is_right)
        self.assertTrue(nothing.is_nothing)

        self.assertFalse(TUtils.is_bad(Right(1)))
        self.assertTrue(TUtils.is_bad(Left(0)))
        self.assertTrue(TUtils.is_bad(Nothing()))

    def test_chain_right(self):
        res = TUtils.unit(2).map(lambda x: x + 1).bind(lambda x: Right(x + 1)).unfold(right=lambda x: x ** 2)
        self.assertEqual(res, 16)

        res = Right(1).map(lambda x: x + 1).bind(lambda x: Right(x + 1)).get_or_else(100)
        self.assertEqual(res, 3)

        res = (
            Right(0)
            .map(lambda x: x + 1)
            .recover_from_left(lambda _: 100)
            .bind(lambda x: TUtils.unit(x + 1))
            .map(lambda x: x + 1)
            .recover_from_nothing(lambda: 1000)
            .bind(lambda x: Right(x + 1))
            .unfold(right=lambda x: x ** 2)
        )
        self.assertEqual(res, 16)

    def test_chain_left(self):
        res = Left(1).map(lambda x: x + 1).bind(lambda x: Right(x + 1))
        self.assertIsInstance(res, Left)

        res = Left(1).map(lambda x: x + 1).bind(lambda x: Right(x + 1)).get_or_else(100)
        self.assertEqual(res, 100)

        res = Left("Some error").map(lambda x: x + 1).bind(lambda x: Right(x + 1)).unfold(left=lambda x: [x])
        self.assertEqual(res, ["Some error"])

        res = (
            Left("Some error")
            .map(lambda x: x + 1)
            .recover_from_left(lambda _: 100)
            .recover_from_nothing(lambda: 1000)
            .recover_from_left(lambda _: 200)
            .unfold(right=lambda x: [x])
        )
        self.assertEqual(res, [100])

    def test_chain_nothing(self):
        res = Nothing().map(lambda x: x + 1).bind(lambda x: Right(x + 1))
        self.assertIsInstance(res, Nothing)

        res = Nothing().map(lambda x: x + 1).bind(lambda x: Right(x + 1)).get_or_else(0)
        self.assertEqual(res, 0)

        res = (
            Nothing()
            .map(lambda x: x + 1)
            .recover_from_left(lambda _: 100)
            .recover_from_nothing(lambda: 1000)
            .bind(lambda x: Right(x + 1))
            .recover_from_nothing(lambda: 1)
            .unfold()
        )
        self.assertEqual(res, 1001)

    def test_chains_violations(self):
        def fn_monadic(x):
            return Right(x)

        async def fn_async(x):
            return x

        @impure
        def fn_impure(a):
            return a

        with self.assertRaises(MonadError):
            Right(1).map(fn_monadic)
        with self.assertRaises(MonadError):
            Right(1).map(fn_async)
        with self.assertRaises(MonadError):
            Right(1).map(fn_impure)

    def test_from_nullable(self):
        self.assertIsInstance(TUtils.from_nullable(None), Nothing)
        self.assertIsInstance(TUtils.from_nullable({"a": 1}, predicate=lambda d: d.get("b")), Nothing)
        self.assertIsInstance(TUtils.from_nullable({"a": 1}, predicate=lambda d: d.get("a")), Right)
        self.assertIsInstance(TUtils.from_nullable(1, predicate=lambda _: False), Nothing)
        self.assertIsInstance(TUtils.from_nullable(None, predicate=lambda a: a is None), Right)

    def test_from_try(self):
        @TUtils.from_try
        def test_from_try(a):
            return a ** 2

        res = test_from_try("1").map(lambda x: x + 1).bind(lambda x: Right(x))
        self.assertTrue(TUtils.is_bad(res))
        self.assertTrue(res.unfold(left=lambda e: isinstance(e, TypeError)))

        res = test_from_try(10).map(lambda x: x + 1).bind(lambda x: Right(x + 1))
        self.assertFalse(TUtils.is_bad(res))
        self.assertEqual(res.unfold(right=lambda x: x + 1), 103)

    def test_closer(self):
        @TUtils.closer
        def test_closer(a: int, b: int, c: int) -> int:
            return a + b + c

        self.assertIsInstance(test_closer(Left(1), 2, 3), Left)
        self.assertIsInstance(test_closer(1, 2, Nothing()), Nothing)
        self.assertIsInstance(test_closer(1, Left(2), Nothing()), Left)
        self.assertEqual(test_closer(Right(1), Right(2), Right(3)), 6)
        self.assertEqual(test_closer(1, 2, 3), 6)
        self.assertEqual(test_closer(1, Right(2), 3), 6)

    def test_curry_basic(self):
        @curry
        def for_curry_one(a: int, b: int, c: int = 0, d: int = 0) -> list[int]:
            return [a, b, c, d]

        @curry
        def for_curry_two(a: int, b: int, *args, **kwargs) -> list:
            return [a, b, args, kwargs]

        @curry
        def for_curry_three(a: int, *, b: int) -> int:
            return a + b

        self.assertEqual(for_curry_one(1)(2)(3)(4), [1, 2, 3, 4])
        self.assertEqual(for_curry_one(1)(2)(), [1, 2, 0, 0])
        self.assertEqual(for_curry_one()(b=2, a=1), [1, 2, 0, 0])
        self.assertEqual(for_curry_one(1, 2)(c=3)(), [1, 2, 3, 0])
        self.assertEqual(for_curry_one(1, 2)(d=3)(), [1, 2, 0, 3])

        res = for_curry_two(1, b=2)
        self.assertTrue(callable(for_curry_two))
        res = res(0, 0)
        self.assertTrue(callable(for_curry_two))
        res = res(another=10)
        self.assertEqual(res, [1, 2, (0, 0), {'another': 10}])
        res = for_curry_two(b=2)(a=1)
        self.assertEqual(res.run_for_var(), [1, 2, (), {}])

        with self.assertRaises(CurryBadArguments):
            for_curry_three(1)(2)  # signature of the original function are preserved - the second arg is only named
        self.assertEqual(for_curry_three(1)(b=2), 3)

    def test_lift(self):
        @curry
        def for_curry(a: int, b: int, c: int = 0, d: int = 0) -> list[int]:
            return [a, b, c, d]

        res = TUtils.lift(for_curry, Right(1), Right(2), Right(3), Right(4))
        self.assertEqual(res.unfold(), [1, 2, 3, 4])

        res = TUtils.lift(for_curry, Right(1), Left('some error'), Right(3), Right(4))
        self.assertEqual(res.unfold(), 'some error')


class TestAsyncCurry(unittest.IsolatedAsyncioTestCase):
    async def test_async_curry(self):
        @async_curry
        async def for_curry(a: int, b: int, c: int = 0, d: int = 0) -> list[int]:
            await asyncio.sleep(0)
            return [a, b, c, d]

        res = await for_curry(1)
        res = await res(2)
        res = await res(3)
        res = await res(4)
        self.assertEqual(res, [1, 2, 3, 4])

        res = await for_curry()
        res = await res(b=2, a=1)
        self.assertEqual(res, [1, 2, 0, 0])


if __name__ == "__main__":
    unittest.main()

import unittest

from mafunca.maybe import Just, Nothing, of, nullable, nullable_yield, ap, lift, lift2, lift3
from mafunca.specials import impure
from mafunca.common.exceptions import MonadError


class TestMaybe(unittest.TestCase):
    def test_introspection(self):
        right = Just(1)
        self.assertTrue(right.is_just)
        self.assertFalse(right.is_nothing)

        from_unit = of(1)
        self.assertTrue(from_unit.is_just)
        self.assertFalse(from_unit.is_nothing)

        err = Nothing()
        self.assertFalse(err.is_just)
        self.assertTrue(err.is_nothing)

    def test_just_chains(self):
        res = of(2).map(lambda x: x + 1).bind(lambda x: Just(x + 1))
        res = res.unfold(just=lambda x: x ** 2, nothing=lambda: None)
        self.assertEqual(res, 16)

        res = Just(1).map(lambda x: x + 1).bind(lambda x: Just(x + 1)).get_or_else(100)
        self.assertEqual(res, 3)

        res = Just(1).map(lambda x: x + 1).map(lambda x: Just(x + 1)).unfold(just=lambda v: v, nothing=lambda: None)
        self.assertIsInstance(res, Just)
        self.assertEqual(res.get_or_else(100), 3)

        res = of(2).bind(lambda _: Nothing()).map(lambda x: x + 1)
        self.assertIsInstance(res, Nothing)
        res = res.unfold(just=lambda v: v, nothing=lambda: None)
        self.assertTrue(res is None)

    def test_nothing_chains(self):
        res = Nothing().map(lambda x: x + 1).bind(lambda x: Just(x + 1))
        self.assertIsInstance(res, Nothing)

        res = Nothing().map(lambda x: x + 1).bind(lambda x: Just(x + 1)).get_or_else(100)
        self.assertEqual(res, 100)

    def test_violations(self):
        @impure
        def fn_impure(a):
            return a

        with self.assertRaises(MonadError):
            Just(1).map(fn_impure)

    def test_nullable(self):
        res = nullable(1).map(lambda x: x + 1).bind(lambda x: Just(x))
        self.assertTrue(res.is_just)
        self.assertEqual(res.get_or_else(100), 2)

        res = nullable(None).map(lambda x: x + 1).bind(lambda x: Just(x))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)

        res = nullable([], is_nullable=lambda lst: len(lst) == 0).map(lambda x: x + 1).bind(lambda x: Just(x))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)

    def test_nullable_yield(self):
        res = nullable_yield((i for i in range(10)), lambda v: v % 2 == 0)
        res = list((m for m in res if m.is_nothing))
        self.assertEqual(len(res), 5)

        res = [1, None, 2, None, 3]
        res = nullable_yield(res)
        res = list(m.get_or_else(100) for m in res if m.is_just)
        self.assertEqual(res, [1, 2, 3])

    def test_ap(self):
        def one(a):
            return [a]

        res = ap(Just(one), Just(10)).get_or_else(0)
        self.assertEqual(res, [10])
        res = ap(Just(one), Nothing())
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(10), 10)
        res = ap(Nothing(), Just(10))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(0), 0)

    def test_lift2(self):
        def two(a, b):
            return [a, b]

        res = lift2(two, Just(1), Just(2)).get_or_else(0)
        self.assertEqual(res, [1, 2])
        res = lift2(two, Just(1), Nothing())
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = lift2(two, Nothing(), Just(2)).get_or_else(0)
        self.assertEqual(res, 0)

    def test_lift3(self):
        def three(a, b, c):
            return [a, b, c]

        res = lift3(three, Just(1), Just(2), Just(3)).get_or_else(0)
        self.assertEqual(res, [1, 2, 3])
        res = lift3(three, Just(1), Nothing(), Just(3))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = lift3(three, Just(1), Nothing(), Just(3)).get_or_else(0)
        self.assertEqual(res, 0)

    def test_lift(self):
        def many(a, b, c, d, e):
            return [a, b, c, d, e]

        res = lift(many, Just(1), Just(2), Just(3), Just(4), Just(5))
        res = res.unfold(just=lambda v: v, nothing=lambda: None)
        self.assertEqual(res, [1, 2, 3, 4, 5])
        res = lift(many, Just(1), Nothing(), Just(3), Just(4), Just(5))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = lift(many, Just(1), Nothing(), Just(3), Just(4), Just(5)).get_or_else(0)
        self.assertEqual(res, 0)


if __name__ == "__main__":
    unittest.main()

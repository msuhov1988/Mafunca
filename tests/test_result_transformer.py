import unittest

from mafunca.result import Ok, Err
from mafunca.maybe import Just, Nothing
from mafunca.result_transformer import ResultMaybeT, from_null, from_try, ap, lift2, lift3, lift4, lift
from mafunca.specials import impure
from mafunca.curry import curry
from mafunca.common.exceptions import MonadError


class TestResultMaybeT(unittest.TestCase):
    def test_introspection_forward(self):
        res = ResultMaybeT(Ok(Just(3)))
        self.assertTrue(res.inner.is_ok)
        self.assertFalse(res.inner.is_error)
        self.assertTrue(res.inner.value.is_just)
        self.assertFalse(res.inner.value.is_nothing)
        self.assertTrue(res.is_just)

        res = ResultMaybeT(Ok(Nothing()))
        self.assertTrue(res.inner.is_ok)
        self.assertFalse(res.inner.is_error)
        self.assertTrue(res.inner.value.is_nothing)
        self.assertFalse(res.inner.value.is_just)
        self.assertTrue(res.is_nothing)

        res = ResultMaybeT(Err(None))
        self.assertTrue(res.inner.is_error)
        self.assertFalse(res.inner.is_ok)
        self.assertTrue(res.is_error)

    def test_introspection_value_methods(self):
        res = ResultMaybeT.just(3)
        self.assertTrue(res.inner.is_ok)
        self.assertFalse(res.inner.is_error)
        self.assertTrue(res.inner.value.is_just)
        self.assertFalse(res.inner.value.is_nothing)
        self.assertTrue(res.is_just)

        res = ResultMaybeT.nothing()
        self.assertTrue(res.inner.is_ok)
        self.assertFalse(res.inner.is_error)
        self.assertTrue(res.inner.value.is_nothing)
        self.assertFalse(res.inner.value.is_just)
        self.assertTrue(res.is_nothing)

        res = ResultMaybeT.error(None)
        self.assertTrue(res.inner.is_error)
        self.assertFalse(res.inner.is_ok)
        self.assertTrue(res.is_error)

    def test_introspection_wraps(self):
        res = ResultMaybeT.wrap_maybe(Just(3))
        self.assertTrue(res.inner.is_ok)
        self.assertFalse(res.inner.is_error)
        self.assertTrue(res.inner.value.is_just)
        self.assertFalse(res.inner.value.is_nothing)
        self.assertTrue(res.is_just)

        res = ResultMaybeT.wrap_maybe(Nothing())
        self.assertTrue(res.inner.is_ok)
        self.assertFalse(res.inner.is_error)
        self.assertTrue(res.inner.value.is_nothing)
        self.assertFalse(res.inner.value.is_just)
        self.assertTrue(res.is_nothing)

        res = ResultMaybeT.wrap_result(Ok(3))
        self.assertTrue(res.inner.is_ok)
        self.assertFalse(res.inner.is_error)
        self.assertTrue(res.inner.value.is_just)
        self.assertFalse(res.inner.value.is_nothing)
        self.assertTrue(res.is_just)

        res = ResultMaybeT.wrap_result(Err(None))
        self.assertTrue(res.inner.is_error)
        self.assertFalse(res.inner.is_ok)
        self.assertTrue(res.is_error)

    def test_map_bind(self):
        res = ResultMaybeT.just(0).map(lambda x: x + 1).bind(lambda x: ResultMaybeT.just(x + 1)).map(lambda x: x + 1)
        self.assertEqual(res.get_or_else(100), 3)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: None)
        self.assertEqual(res, 9)

        res = ResultMaybeT.just(0).map(lambda x: x + 1).bind(lambda _: ResultMaybeT.nothing()).map(lambda x: x + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: None)
        self.assertEqual(res, 0)

        res = ResultMaybeT.nothing().map(lambda x: x + 1).bind(lambda x: ResultMaybeT.just(x + 1)).map(lambda x: x + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: None)
        self.assertEqual(res, 0)

        res = ResultMaybeT.just(0).map(lambda x: x + 1).bind(lambda x: ResultMaybeT.error(x + 1)).map(lambda x: x + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: 100)
        self.assertEqual(res, 100)

        res = ResultMaybeT.error(0).bind(lambda x: ResultMaybeT.just(x + 1)).bind(lambda x: ResultMaybeT.error(x + 1))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 0)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: 100)
        self.assertEqual(res, 100)

    def test_map_maybe_and_result(self):
        res = ResultMaybeT.just(0).map_maybe(lambda x: Just(x + 1)).bind(lambda x: ResultMaybeT.just(x + 1))
        self.assertEqual(res.get_or_else(100), 2)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: None)
        self.assertEqual(res, 4)

        res = ResultMaybeT.just(0).map_maybe(lambda _: Nothing()).map(lambda x: x + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: None)
        self.assertEqual(res, 0)

        res = ResultMaybeT.just(0).map_result(lambda x: Ok(x + 1)).bind(lambda x: ResultMaybeT.just(x + 1))
        self.assertEqual(res.get_or_else(100), 2)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: None)
        self.assertEqual(res, 4)

        res = ResultMaybeT.just(0).map_result(lambda x: Err(x + 1)).map(lambda x: x + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 1)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda e: e + 1)
        self.assertEqual(res, 2)

    def test_map_error(self):
        res = ResultMaybeT.just(0).map_error(lambda e: e + 1).bind(lambda x: ResultMaybeT.just(x + 10))
        self.assertEqual(res.get_or_else(100), 10)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: None)
        self.assertEqual(res, 100)

        res = ResultMaybeT.error(0).bind(lambda x: ResultMaybeT.just(x + 10)).map_error(lambda e: e + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 1)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda e: e + 1)
        self.assertEqual(res, 2)

        res = ResultMaybeT.just(0).bind(lambda x: ResultMaybeT.error(x + 1)).map_error(lambda e: e + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda e: e + 1)
        self.assertEqual(res, 3)

        res = ResultMaybeT.just(0).map_result(lambda x: Err(x + 1)).map_error(lambda e: e + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda e: e + 1)
        self.assertEqual(res, 3)

        res = ResultMaybeT.just(0).map_maybe(lambda _: Nothing()).map_error(lambda e: e + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(ok=lambda m: m.map(lambda x: x ** 2).get_or_else(0), err=lambda _: None)
        self.assertEqual(res, 0)

    def test_violations(self):
        @impure
        def fn_impure(a):
            return a

        with self.assertRaises(MonadError):
            ResultMaybeT.just(1).map(fn_impure)

    def test_from_null(self):
        res = from_null(1).map(lambda x: x + 1).bind(lambda x: ResultMaybeT.just(x + 1))
        self.assertTrue(res.is_just)
        self.assertEqual(res.get_or_else(100), 3)

        res = from_null(None).map(lambda x: x + 1).bind(lambda x: ResultMaybeT.just(x + 1))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)

        res = from_null([], is_nullable=lambda lst: len(lst) == 0).bind(lambda x: ResultMaybeT.just(x + 1))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)

    def test_from_try_errors(self):
        @from_try()
        def test(a):
            if a == 0:
                return None
            return a ** 2

        res = test("1").map(lambda x: x + 1).bind(lambda x: ResultMaybeT.just(x + 1))  # noqa
        self.assertTrue(res.is_error)
        self.assertTrue(res.unfold(ok=lambda _: False, err=lambda e: isinstance(e, TypeError)))

        res = test(0).map(lambda x: x + 1).bind(lambda x: ResultMaybeT.just(x + 1))
        self.assertTrue(res.is_nothing)
        self.assertTrue(res.unfold(ok=lambda m: m.get_or_else(True), err=lambda _: False))

        res = test(10).map(lambda x: x + 1).bind(lambda x: ResultMaybeT.just(x + 1))
        self.assertTrue(res.is_just)
        self.assertEqual(res.unfold(ok=lambda m: m.get_or_else(0), err=lambda _: 0), 102)

    def test_from_try_custom_nullable(self):
        @from_try(lambda lst: len(lst) == 0)
        def test(a):
            return [*a, *a]

        res = test([1]).map(lambda x: [*x, 1])  # noqa
        self.assertTrue(res.is_just)
        self.assertEqual(res.get_or_else(0), [1, 1, 1])

        res = test([]).map(lambda x: [*x, 1])  # noqa
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(0), 0)

    def test_from_try_monad_error(self):
        @from_try()
        def raiser(a):
            a = a + 1  # noqa
            raise MonadError("test", "test", "test")

        with self.assertRaises(MonadError):
            raiser(1)

    def test_ap(self):
        def one(a):
            return [a]

        res = ap(ResultMaybeT.just(one), ResultMaybeT.just(10)).get_or_else(0)
        self.assertEqual(res, [10])

        res = ap(ResultMaybeT.just(one), ResultMaybeT.error(10))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 10)

        res = ap(ResultMaybeT.error(0), ResultMaybeT.just(10))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 0)

        res = ap(ResultMaybeT.nothing(), ResultMaybeT.just(10))
        self.assertTrue(res.is_nothing)
        res = ap(ResultMaybeT.just(10), ResultMaybeT.nothing())
        self.assertTrue(res.is_nothing)

    def test_lift2(self):
        def two(a, b):
            return [a, b]

        res = lift2(two, ResultMaybeT.just(1), ResultMaybeT.just(2)).get_or_else([0])
        self.assertEqual(res, [1, 2])
        res = lift2(two, ResultMaybeT.just(1), ResultMaybeT.error(2))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)
        res = lift2(two, ResultMaybeT.just(1), ResultMaybeT.nothing())
        self.assertTrue(res.is_nothing)

    def test_lift3(self):
        def three(a, b, c):
            return [a, b, c]

        res = lift3(three, ResultMaybeT.just(1), ResultMaybeT.just(2), ResultMaybeT.just(3)).get_or_else([0])
        self.assertEqual(res, [1, 2, 3])

        res = lift3(three, ResultMaybeT.just(1), ResultMaybeT.error(2), ResultMaybeT.error(3))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)

        res = lift3(three, ResultMaybeT.just(1), ResultMaybeT.nothing(), ResultMaybeT.just(3))
        self.assertTrue(res.is_nothing)

        res = lift3(three, ResultMaybeT.nothing(), ResultMaybeT.error(2), ResultMaybeT.just(3))
        self.assertTrue(res.is_nothing)

        res = lift3(three, ResultMaybeT.just(3), ResultMaybeT.error(2), ResultMaybeT.nothing())
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)

    def test_lift4(self):
        def four(a, b, c, d):
            return [a, b, c, d]

        just = ResultMaybeT.just
        nothing = ResultMaybeT.nothing
        error = ResultMaybeT.error

        res = lift4(four, just(1), just(2), just(3), just(4)).get_or_else([0])
        self.assertEqual(res, [1, 2, 3, 4])

        res = lift4(four, just(1), error(2), error(3), just(4))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)

        res = lift4(four, just(1), nothing(), just(3), just(4))
        self.assertTrue(res.is_nothing)

        res = lift4(four, nothing(), error(2), just(3), just(4))
        self.assertTrue(res.is_nothing)

        res = lift4(four, just(3), error(2), nothing(), just(4))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)

        four = impure(four)
        with self.assertRaises(MonadError):
            lift4(four, just(1), just(2), just(3), just(4))

    def test_lift(self):
        def many(a, b, c, d, e):
            return [a, b, c, d, e]
        
        just = ResultMaybeT.just
        err = ResultMaybeT.error
        nothing = ResultMaybeT.nothing

        res = lift(many, just(1), just(2), just(3), just(4), just(5))
        res = res.unfold(ok=lambda m: m.get_or_else(0), err=lambda _: None)
        self.assertEqual(res, [1, 2, 3, 4, 5])

        res = lift(many, just(1), err(2), just(3), just(4), just(5))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)

        res = lift(many, just(1), nothing(), just(3), just(4), just(5))
        self.assertTrue(res.is_nothing)

        res = lift(many, just(1), err(2), nothing(), just(4), just(5))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.error, 2)

        res = lift(many, just(1), nothing(), err(3), just(4), just(5))
        self.assertTrue(res.is_nothing)

    def test_lift_partial(self):
        def many(a, b, c, d, e):
            return [a, b, c, d, e]

        just = ResultMaybeT.just
        err = ResultMaybeT.error

        res = lift(many, just(1), just(2), just(3))
        res = ap(res, just(4))
        res = ap(res, just(5)).get_or_else([])
        self.assertEqual(res, [1, 2, 3, 4, 5])

        res = lift(many, err(None), just(2), just(3))
        res = ap(res, just(4))
        res = ap(res, just(5))
        self.assertTrue(res.is_error)

    def test_curry_impurity(self):
        @curry
        @impure
        def test(a, b):
            return a + b

        just = ResultMaybeT.just

        with self.assertRaises(MonadError):
            lift(test, just(1), just(2))


if __name__ == "__main__":
    unittest.main()

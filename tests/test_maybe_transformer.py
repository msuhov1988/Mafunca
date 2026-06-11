import unittest

from mafunca.result import Ok, Err
from mafunca.maybe import Just, Nothing
from mafunca.maybe_transformer import TMaybeR, from_null, from_try, ap, lift2, lift3, lift4, lift
from mafunca.specials import impure
from mafunca.curry import curry
from mafunca.common.exceptions import MonadError


class TestMaybeResultT(unittest.TestCase):
    def test_introspection_forward(self):
        res = TMaybeR(Just(Ok(3)))
        self.assertTrue(res.inner.value.is_ok)
        self.assertFalse(res.inner.value.is_error)
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.is_ok)

        res = TMaybeR(Just(Err(None)))
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_error)
        self.assertFalse(res.inner.value.is_ok)
        self.assertTrue(res.is_error)

        res = TMaybeR(Nothing())
        self.assertTrue(res.inner.is_nothing)
        self.assertFalse(res.inner.is_just)
        self.assertTrue(res.is_nothing)

    def test_introspection_value_methods(self):
        res = TMaybeR.ok(3)
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_ok)
        self.assertFalse(res.inner.value.is_error)
        self.assertTrue(res.is_ok)

        res = TMaybeR.error(None)
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_error)
        self.assertFalse(res.inner.value.is_ok)
        self.assertTrue(res.is_error)

        res = TMaybeR.nothing()
        self.assertTrue(res.inner.is_nothing)
        self.assertFalse(res.inner.is_just)
        self.assertTrue(res.is_nothing)

    def test_introspection_wraps(self):
        res = TMaybeR.wrap_maybe(Just(3))
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_ok)
        self.assertFalse(res.inner.value.is_error)
        self.assertTrue(res.is_ok)

        res = TMaybeR.wrap_maybe(Nothing())
        self.assertTrue(res.inner.is_nothing)
        self.assertFalse(res.inner.is_just)
        self.assertTrue(res.is_nothing)

        res = TMaybeR.wrap_result(Ok(3))
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_ok)
        self.assertFalse(res.inner.value.is_error)
        self.assertTrue(res.is_ok)

        res = TMaybeR.wrap_result(Err(None))
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_error)
        self.assertFalse(res.inner.value.is_ok)
        self.assertTrue(res.is_error)

    def test_map_bind(self):
        res = TMaybeR.ok(0).map(lambda x: x + 1).bind(lambda x: TMaybeR.ok(x + 1)).map(lambda x: x + 1)
        self.assertEqual(res.get_or_else(100), 3)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 9)

        res = TMaybeR.ok(0).map(lambda x: x + 1).bind(lambda _: TMaybeR.nothing()).map(lambda x: x + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, -1)

        res = TMaybeR.nothing().map(lambda x: x + 1).bind(lambda x: TMaybeR.ok(x + 1)).map(lambda x: x + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, -1)

        res = TMaybeR.ok(0).map(lambda x: x + 1).bind(lambda x: TMaybeR.error(x + 1)).map(lambda x: x + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 0)

        res = TMaybeR.error(0).bind(lambda x: TMaybeR.ok(x + 1)).bind(lambda x: TMaybeR.error(x + 1))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 0)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(100), nothing=lambda: -1)
        self.assertEqual(res, 100)

    def test_map_maybe_and_result(self):
        res = TMaybeR.ok(0).map_maybe(lambda x: Just(x + 1)).bind(lambda x: TMaybeR.ok(x + 1))
        self.assertEqual(res.get_or_else(100), 2)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 4)

        res = TMaybeR.ok(0).map_maybe(lambda _: Nothing()).map(lambda x: x + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 100)

        res = TMaybeR.ok(0).map_result(lambda x: Ok(x + 1)).bind(lambda x: TMaybeR.ok(x + 1))
        self.assertEqual(res.get_or_else(100), 2)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 4)

        res = TMaybeR.ok(0).map_result(lambda x: Err(x + 1)).map(lambda x: x + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 1)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 0)

    def test_map_error(self):
        res = TMaybeR.ok(0).map_error(lambda e: e + 1).bind(lambda x: TMaybeR.ok(x + 10))
        self.assertEqual(res.get_or_else(100), 10)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 100)

        res = TMaybeR.error(0).bind(lambda x: TMaybeR.ok(x + 10)).map_error(lambda e: e + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 1)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 0)

        res = TMaybeR.ok(0).bind(lambda x: TMaybeR.error(x + 1)).map_error(lambda e: e + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 0)

        res = TMaybeR.ok(0).map_result(lambda x: Err(x + 1)).map_error(lambda e: e + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 0)

        res = TMaybeR.ok(0).map_maybe(lambda _: Nothing()).map_error(lambda e: e + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, -1)

    def test_violations(self):
        @impure
        def fn_impure(a):
            return a

        with self.assertRaises(MonadError):
            TMaybeR.ok(1).map(fn_impure)

    def test_from_null(self):
        res = from_null(1).map(lambda x: x + 1).bind(lambda x: TMaybeR.ok(x + 1))
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(100), 3)

        res = from_null(None).map(lambda x: x + 1).bind(lambda x: TMaybeR.ok(x + 1))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)

        res = from_null([], is_nullable=lambda lst: len(lst) == 0).bind(lambda x: TMaybeR.ok(x + 1))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)

    def test_from_try_errors(self):
        @from_try()
        def test(a):
            if a == 0:
                return None
            return a ** 2

        res = test("1").map(lambda x: x + 1).bind(lambda x: TMaybeR.ok(x + 1))  # noqa
        self.assertTrue(res.is_error)
        self.assertTrue(res.unfold(just=lambda m: m.get_or_else(True), nothing=lambda: False))

        res = test(0).map(lambda x: x + 1).bind(lambda x: TMaybeR.ok(x + 1))
        self.assertTrue(res.is_nothing)
        self.assertTrue(res.unfold(just=lambda m: m.get_or_else(False), nothing=lambda: True))

        res = test(10).map(lambda x: x + 1).bind(lambda x: TMaybeR.ok(x + 1))
        self.assertTrue(res.is_ok)
        self.assertEqual(res.unfold(just=lambda m: m.get_or_else(0), nothing=lambda: -1), 102)

    def test_from_try_custom_nullable(self):
        @from_try(lambda lst: len(lst) == 0)
        def test(a):
            return [*a, *a]

        res = test([1]).map(lambda x: [*x, 1])  # noqa
        self.assertTrue(res.is_ok)
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

        res = ap(TMaybeR.ok(one), TMaybeR.ok(10)).get_or_else(0)
        self.assertEqual(res, [10])

        res = ap(TMaybeR.ok(one), TMaybeR.error(10))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 10)

        res = ap(TMaybeR.error(0), TMaybeR.ok(10))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 0)

        res = ap(TMaybeR.nothing(), TMaybeR.ok(10))
        self.assertTrue(res.is_nothing)
        res = ap(TMaybeR.ok(10), TMaybeR.nothing())
        self.assertTrue(res.is_nothing)

    def test_lift2(self):
        def two(a, b):
            return [a, b]

        res = lift2(two, TMaybeR.ok(1), TMaybeR.ok(2)).get_or_else([0])
        self.assertEqual(res, [1, 2])
        res = lift2(two, TMaybeR.ok(1), TMaybeR.error(2))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)
        res = lift2(two, TMaybeR.ok(1), TMaybeR.nothing())
        self.assertTrue(res.is_nothing)

    def test_lift3(self):
        def three(a, b, c):
            return [a, b, c]

        res = lift3(three, TMaybeR.ok(1), TMaybeR.ok(2), TMaybeR.ok(3)).get_or_else([0])
        self.assertEqual(res, [1, 2, 3])

        res = lift3(three, TMaybeR.ok(1), TMaybeR.error(2), TMaybeR.error(3))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)

        res = lift3(three, TMaybeR.ok(1), TMaybeR.nothing(), TMaybeR.ok(3))
        self.assertTrue(res.is_nothing)

        res = lift3(three, TMaybeR.nothing(), TMaybeR.error(2), TMaybeR.ok(3))
        self.assertTrue(res.is_nothing)

        res = lift3(three, TMaybeR.ok(3), TMaybeR.error(2), TMaybeR.nothing())
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)

    def test_lift4(self):
        def four(a, b, c, d):
            return [a, b, c, d]

        ok = TMaybeR.ok
        error = TMaybeR.error
        nothing = TMaybeR.nothing

        res = lift4(four, ok(1), ok(2), ok(3), ok(4)).get_or_else([0])
        self.assertEqual(res, [1, 2, 3, 4])

        res = lift4(four, ok(1), error(2), error(3), ok(4))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)

        res = lift4(four, ok(1), nothing(), ok(3), ok(4))
        self.assertTrue(res.is_nothing)

        res = lift4(four, nothing(), error(2), ok(3), ok(4))
        self.assertTrue(res.is_nothing)

        res = lift4(four, ok(3), error(2), nothing(), ok(4))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)

        four = impure(four)
        with self.assertRaises(MonadError):
            lift4(four, ok(1), ok(2), ok(3), ok(4))

    def test_lift(self):
        def many(a, b, c, d, e):
            return [a, b, c, d, e]

        just = TMaybeR.ok
        err = TMaybeR.error
        nothing = TMaybeR.nothing

        res = lift(many, just(1), just(2), just(3), just(4), just(5))
        res = res.unfold(just=lambda m: m.get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, [1, 2, 3, 4, 5])

        res = lift(many, just(1), err(2), just(3), just(4), just(5))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)

        res = lift(many, just(1), nothing(), just(3), just(4), just(5))
        self.assertTrue(res.is_nothing)

        res = lift(many, just(1), err(2), nothing(), just(4), just(5))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)

        res = lift(many, just(1), nothing(), err(3), just(4), just(5))
        self.assertTrue(res.is_nothing)

    def test_lift_partial(self):
        def many(a, b, c, d, e):
            return [a, b, c, d, e]

        just = TMaybeR.ok
        err = TMaybeR.error

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

        just = TMaybeR.ok

        with self.assertRaises(MonadError):
            lift(test, just(1), just(2))


if __name__ == "__main__":
    unittest.main()

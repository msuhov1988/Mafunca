import unittest

from mafunca.result import Ok, Err
from mafunca.maybe import Just, Nothing
from mafunca.maybe_transformer import MaybeT, from_null, from_try, ap, lift2, lift3, lift4, lift
from mafunca.maybe_transformer import ok_of, error_of, nothing_of, result_of, maybe_of
from mafunca.common.exceptions import MonadError


class TestMaybeResultT(unittest.TestCase):
    def test_introspection_forward(self):
        res = MaybeT(Just(Ok(3)))
        self.assertTrue(res.inner.value.is_ok)
        self.assertFalse(res.inner.value.is_error)
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.is_ok)

        res = MaybeT(Just(Err(None)))
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_error)
        self.assertFalse(res.inner.value.is_ok)
        self.assertTrue(res.is_error)

        res = MaybeT(Nothing())
        self.assertTrue(res.inner.is_nothing)
        self.assertFalse(res.inner.is_just)
        self.assertTrue(res.is_nothing)

    def test_introspection_value_methods(self):
        res = ok_of(3)
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_ok)
        self.assertFalse(res.inner.value.is_error)
        self.assertTrue(res.is_ok)

        res = error_of(None)
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_error)
        self.assertFalse(res.inner.value.is_ok)
        self.assertTrue(res.is_error)

        res = nothing_of()
        self.assertTrue(res.inner.is_nothing)
        self.assertFalse(res.inner.is_just)
        self.assertTrue(res.is_nothing)

    def test_introspection_wraps(self):
        res = maybe_of(Just(3))
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_ok)
        self.assertFalse(res.inner.value.is_error)
        self.assertTrue(res.is_ok)

        res = maybe_of(Nothing())
        self.assertTrue(res.inner.is_nothing)
        self.assertFalse(res.inner.is_just)
        self.assertTrue(res.is_nothing)

        res = result_of(Ok(3))
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_ok)
        self.assertFalse(res.inner.value.is_error)
        self.assertTrue(res.is_ok)

        res = result_of(Err(None))
        self.assertTrue(res.inner.is_just)
        self.assertFalse(res.inner.is_nothing)
        self.assertTrue(res.inner.value.is_error)
        self.assertFalse(res.inner.value.is_ok)
        self.assertTrue(res.is_error)

    def test_map_bind(self):
        res = ok_of(0).map(lambda x: x + 1).bind(lambda x: ok_of(x + 1)).map(lambda x: x + 1)
        self.assertEqual(res.get_or_else(100), 3)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 9)

        res = ok_of(0).map(lambda x: x + 1).bind(lambda _: nothing_of()).map(lambda x: x + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, -1)

        res = nothing_of().map(lambda x: x + 1).bind(lambda x: ok_of(x + 1)).map(lambda x: x + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, -1)

        res = ok_of(0).map(lambda x: x + 1).bind(lambda x: error_of(x + 1)).map(lambda x: x + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 0)

        res = error_of(0).bind(lambda x: ok_of(x + 1)).bind(lambda x: error_of(x + 1))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 0)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(100), nothing=lambda: -1)
        self.assertEqual(res, 100)

    def test_map_maybe_and_result(self):
        res = ok_of(0).map_maybe(lambda x: Just(x + 1)).bind(lambda x: ok_of(x + 1))
        self.assertEqual(res.get_or_else(100), 2)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 4)

        res = ok_of(0).map_maybe(lambda _: Nothing()).map(lambda x: x + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 100)

        res = ok_of(0).map_result(lambda x: Ok(x + 1)).bind(lambda x: ok_of(x + 1))
        self.assertEqual(res.get_or_else(100), 2)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 4)

        res = ok_of(0).map_result(lambda x: Err(x + 1)).map(lambda x: x + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 1)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: 100)
        self.assertEqual(res, 0)

    def test_map_error(self):
        res = ok_of(0).map_error(lambda e: e + 1).bind(lambda x: ok_of(x + 10))
        self.assertEqual(res.get_or_else(100), 10)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 100)

        res = error_of(0).bind(lambda x: ok_of(x + 10)).map_error(lambda e: e + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 1)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 0)

        res = ok_of(0).bind(lambda x: error_of(x + 1)).map_error(lambda e: e + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 0)

        res = ok_of(0).map_result(lambda x: Err(x + 1)).map_error(lambda e: e + 1)
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, 0)

        res = ok_of(0).map_maybe(lambda _: Nothing()).map_error(lambda e: e + 1)
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)
        res = res.unfold(just=lambda m: m.map(lambda x: x ** 2).get_or_else(0), nothing=lambda: -1)
        self.assertEqual(res, -1)

    def test_from_null(self):
        res = from_null()(1).map(lambda x: x + 1).bind(lambda x: ok_of(x + 1))
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(100), 3)

        res = from_null()(None).map(lambda x: x + 1).bind(lambda x: ok_of(x + 1))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)

        res = from_null(is_nullable=lambda lst: len(lst) == 0)([]).bind(lambda x: ok_of(x + 1))
        self.assertTrue(res.is_nothing)
        self.assertEqual(res.get_or_else(100), 100)

    def test_from_try_errors(self):
        @from_try()
        def test(a):
            if a == 0:
                return None
            return a ** 2

        res = test("1").map(lambda x: x + 1).bind(lambda x: MaybeT.ok(x + 1))  # noqa
        self.assertTrue(res.is_error)
        self.assertTrue(res.unfold(just=lambda m: m.get_or_else(True), nothing=lambda: False))

        res = test(0).map(lambda x: x + 1).bind(lambda x: ok_of(x + 1))
        self.assertTrue(res.is_nothing)
        self.assertTrue(res.unfold(just=lambda m: m.get_or_else(False), nothing=lambda: True))

        res = test(10).map(lambda x: x + 1).bind(lambda x: ok_of(x + 1))
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
            _ = a + 1
            raise MonadError("test", "test", "test")

        with self.assertRaises(MonadError):
            raiser(1)

    def test_ap(self):
        def one(a):
            return [a]

        res = ap(ok_of(one), ok_of(10)).get_or_else([0])
        self.assertEqual(res, [10])

        res = ap(ok_of(one), error_of(10))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 10)

        res = ap(error_of(0), ok_of(10))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 0)

        res = ap(nothing_of(), ok_of(10))
        self.assertTrue(res.is_nothing)
        res = ap(ok_of(lambda x: x), nothing_of())
        self.assertTrue(res.is_nothing)

    def test_lift2(self):
        def two(a, b):
            return [a, b]

        res = lift2(two, ok_of(1), ok_of(2)).get_or_else([0])
        self.assertEqual(res, [1, 2])
        res = lift2(two, ok_of(1), error_of(2))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)
        res = lift2(two, ok_of(1), nothing_of())
        self.assertTrue(res.is_nothing)

    def test_lift3(self):
        def three(a, b, c):
            return [a, b, c]

        res = lift3(three, ok_of(1), ok_of(2), ok_of(3)).get_or_else([0])
        self.assertEqual(res, [1, 2, 3])

        res = lift3(three, ok_of(1), error_of(2), error_of(3))
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)

        res = lift3(three, ok_of(1), nothing_of(), ok_of(3))
        self.assertTrue(res.is_nothing)

        res = lift3(three, nothing_of(), error_of(2), ok_of(3))
        self.assertTrue(res.is_nothing)

        res = lift3(three, ok_of(3), error_of(2), nothing_of())
        self.assertTrue(res.is_error)
        self.assertEqual(res.inner.value.error, 2)

    def test_lift4(self):
        def four(a, b, c, d):
            return [a, b, c, d]

        ok = ok_of
        error = error_of
        nothing = nothing_of

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

    def test_lift(self):
        def many(a, b, c, d, e):
            return [a, b, c, d, e]

        just = ok_of
        err = error_of
        nothing = nothing_of

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


if __name__ == "__main__":
    unittest.main()

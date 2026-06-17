import unittest

from mafunca.result import Ok, Err, ok_of, from_try, ap, lift, lift2, lift3, lift4
from mafunca.common.exceptions import MonadError


class TestResult(unittest.TestCase):
    def test_introspection(self):
        right = Ok(1)
        self.assertTrue(right.is_ok)
        self.assertFalse(right.is_error)

        from_unit = ok_of(1)
        self.assertTrue(from_unit.is_ok)
        self.assertFalse(from_unit.is_error)

        err = Err(1)
        self.assertFalse(err.is_ok)
        self.assertTrue(err.is_error)

    def test_ok_chains(self):
        res = ok_of(2).map(lambda x: x + 1).bind(lambda x: Ok(x + 1)).unfold(ok=lambda x: x ** 2, err=lambda _: None)
        self.assertEqual(res, 16)

        res = Ok(1).map(lambda x: x + 1).bind(lambda x: Ok(x + 1)).get_or_else(100)
        self.assertEqual(res, 3)

        res = Ok(1).map(lambda x: x + 1).map(lambda x: Ok(x + 1)).unfold(ok=lambda v: v, err=lambda e: e)
        self.assertIsInstance(res, Ok)
        self.assertEqual(res.get_or_else(100), 3)

        res = ok_of(2).bind(lambda _: Err(None)).map(lambda x: x + 1)
        self.assertIsInstance(res, Err)
        res = res.unfold(ok=lambda v: v, err=lambda e: e)
        self.assertTrue(res is None)

        res = ok_of(2).map_error(lambda e: [e]).unfold(ok=lambda v: v, err=lambda e: e)
        self.assertEqual(res, 2)

    def test_err_chains(self):
        res = Err(1).map(lambda x: x + 1).bind(lambda x: Ok(x + 1))
        self.assertIsInstance(res, Err)

        res = Err(1).map(lambda x: x + 1).bind(lambda x: Ok(x + 1)).get_or_else(100)
        self.assertEqual(res, 100)

        res = Err("Some error").map(lambda x: x + 1).bind(lambda x: Ok(x + 1))
        res = res.unfold(ok=lambda x: x ** 2, err=lambda x: [x])
        self.assertEqual(res, ["Some error"])

        res = Err("Some error").map_error(lambda e: [e]).unfold(ok=lambda v: v, err=lambda e: e)
        self.assertEqual(res, ["Some error"])

    def test_from_try(self):
        @from_try
        def test_from_try(a):
            return a ** 2

        res = test_from_try("1").map(lambda x: x + 1).bind(lambda x: Ok(x))
        self.assertTrue(res.is_error)
        self.assertTrue(res.unfold(ok=lambda _: False, err=lambda e: isinstance(e, TypeError)))

        res = test_from_try(10).map(lambda x: x + 1).bind(lambda x: Ok(x + 1))
        self.assertTrue(res.is_ok)
        self.assertEqual(res.unfold(ok=lambda x: x + 1, err=lambda _: 0), 103)

    def test_from_try_monad_error(self):
        @from_try
        def raiser(a):
            _ = a + 1
            raise MonadError("test", "test", "test")

        with self.assertRaises(MonadError):
            raiser(1)

    def test_ap(self):
        def one(a):
            return [a]

        res = ap(Ok(one), Ok(10)).get_or_else(0)
        self.assertEqual(res, [10])
        res = ap(Ok(one), Err(10))
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 10)
        res = ap(Err(0), Ok(10))
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

    def test_lift2(self):
        def two(a, b):
            return [a, b]

        res = lift2(two, Ok(1), Ok(2)).get_or_else([0])
        self.assertEqual(res, [1, 2])
        res = lift2(two, Ok(1), Err(2))
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 2)
        res = lift2(two, Err(1), Ok(2)).get_or_else([0])
        self.assertEqual(res, [0])

    def test_lift3(self):
        def three(a, b, c):
            return [a, b, c]

        res = lift3(three, Ok(1), Ok(2), Ok(3)).get_or_else(0)
        self.assertEqual(res, [1, 2, 3])
        res = lift3(three, Ok(1), Err(2), Err(3))
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 2)
        res = lift3(three, Ok(1), Err(2), Ok(3)).get_or_else(0)
        self.assertEqual(res, 0)

    def test_lift4(self):
        def four(a, b, c, d):
            return [a, b, c, d]

        res = lift4(four, Ok(1), Ok(2), Ok(3), Ok(4)).get_or_else([])
        self.assertEqual(res, [1, 2, 3, 4])
        res = lift4(four, Ok(1), Err(None), Ok(3), Ok(4))
        self.assertTrue(res.is_error)
        self.assertEqual(res.get_or_else(100), 100)
        res = lift4(four, Ok(1), Err(None), Ok(3), Ok(4)).get_or_else(0)
        self.assertEqual(res, 0)

    def test_lift(self):
        def many(a, b, c, d, e):
            return [a, b, c, d, e]

        res = lift(many, Ok(1), Ok(2), Ok(3), Ok(4), Ok(5)).unfold(ok=lambda v: v, err=lambda _: None)
        self.assertEqual(res, [1, 2, 3, 4, 5])
        res = lift(many, Ok(1), Err(2), Ok(3), Ok(4), Ok(5))
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 2)
        res = lift(many, Ok(1), Err(2), Ok(3), Ok(4), Ok(5)).get_or_else(0)
        self.assertEqual(res, 0)


if __name__ == "__main__":
    unittest.main()

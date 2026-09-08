import unittest

from mafunca.common.exceptions import MonadError
from mafunca.common.exceptions import ValidationError, RetryBadPauseError, RetryByExceptionError, RetryByValueError
from mafunca.result import Success, Fail, success, fail
from mafunca.effect_sync import pure, delay, retry
from mafunca.effect_sync import lift2, lift3, lift4
from mafunca.trans_effect_sync import pure_success as lift_pure, pure_fail as lift_error
from mafunca.trans_effect_sync import delay as delay_t, retry as retry_t
from mafunca.trans_effect_sync import lift_effect, pure_result as lift_result
from mafunca.trans_effect_sync import lift2 as lift2_t, lift3 as lift3_t, lift4 as lift4_t
from mafunca.effect_runners import run, run_safe


class TestEffectSync(unittest.TestCase):
    def test_init(self):
        eff = pure(0)
        self.assertEqual(run(eff), 0)

        eff = delay(lambda: 0)
        self.assertEqual(run(eff), 0)

    def test_map(self):
        eff = pure(0).fmap(lambda v: v + 1).fmap(lambda v: v + 1)
        self.assertEqual(run(eff), 2)

        eff = delay(lambda: 0).fmap(lambda v: v + 1).fmap(lambda v: v + 1)
        self.assertEqual(run(eff), 2)

    def test_bind(self):
        eff = pure(0).bind(lambda v: pure(v + 1)).fmap(lambda v: v + 1)
        self.assertEqual(run(eff), 2)

        eff = pure(0).bind(lambda v: delay(lambda: v + 1).fmap(lambda vn: vn + 1))
        self.assertEqual(run(eff), 2)

        eff = delay(lambda: 0).bind(lambda v: pure(v + 1)).fmap(lambda v: v + 1)
        self.assertEqual(run(eff), 2)

        eff = delay(lambda: 0).bind(lambda v: delay(lambda: v + 1).fmap(lambda vn: vn + 1))
        self.assertEqual(run(eff), 2)

        eff = (
            delay(lambda: 0)
            .bind(lambda v: delay(lambda: v + 1).bind(lambda vn: pure(vn + 1)))
        )
        self.assertEqual(run(eff), 2)

    def test_catch(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = delay(lambda: raiser(-10)).catch_fmap(TypeError, lambda _: 0).fmap(lambda v: v + 1)
        self.assertEqual(run(eff), 1)

        eff = delay(lambda: raiser(-10)).fmap(lambda v: v + 1).catch_fmap(TypeError, lambda _: 0)
        self.assertEqual(run(eff), 0)

        eff = delay(lambda: raiser(10)).catch_bind(TypeError, lambda _: pure(0)).fmap(lambda v: v + 1)
        self.assertEqual(run(eff), 11)

        eff = (
            delay(lambda: raiser(-10))
            .bind(lambda v: delay(lambda: v + 100))
            .catch_bind(TypeError, lambda _: pure(0).bind(lambda v: pure(v + 1)))
            .fmap(lambda v: v + 1)
        )
        self.assertEqual(run(eff), 2)

    def test_catch_no_effect_by_exception_type(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = delay(lambda: raiser(-10)).catch_fmap(ValueError, lambda _: 0)
        with self.assertRaises(TypeError):
            run(eff)

    def test_catch_no_effect_by_scope(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = delay(lambda: raiser(-10)).bind(lambda v: pure(v + 1).catch_fmap(TypeError, lambda _: 0))
        with self.assertRaises(TypeError):
            run(eff)

    def test_catch_no_effect_with_no_errors(self):
        eff = pure(0).bind(lambda v: pure(v + 1)).catch_fmap(TypeError, lambda _: 0)
        self.assertEqual(run(eff), 1)

        eff = pure(0).fmap(lambda v: v + 1).catch_bind(TypeError, lambda _: pure(0))
        self.assertEqual(run(eff), 1)

    def test_catch_with_error_in_cather(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        def catcher_raiser(a: int):
            if a < 0:
                raise ValueError("test catcher raise")
            return a


        eff = delay(lambda: raiser(-10)).catch_bind(TypeError, lambda _: delay(lambda: catcher_raiser(-10)))
        with self.assertRaises(ValueError):
            run(eff)

    def test_ensure(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        glb = 0

        def increase():
            nonlocal glb
            glb += 1

        eff = delay(lambda: 0).fmap(lambda v: v + 1).ensure(delay(increase))
        res = run(eff)
        self.assertEqual(res, 1)
        self.assertEqual(glb, 1)

        eff = delay(lambda: raiser(-10)).fmap(lambda v: v + 1).ensure(delay(increase))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 2)

        eff = delay(lambda: raiser(-10)).ensure(delay(increase)).ensure(delay(increase))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 4)

        eff = delay(lambda: raiser(-10)).ensure(delay(increase).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 6)

        eff = pure(0).ensure(delay(increase))
        run(eff)
        self.assertEqual(glb, 7)

    def test_ensure_scopes(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        glb = 0

        def increase():
            nonlocal glb
            glb += 1

        eff = delay(lambda: raiser(-10)).bind(lambda v: pure(v + 1).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 0)

        eff = pure(0).bind(lambda _: delay(lambda: raiser(-10)).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 1)

        eff = (
            pure(0)
            .bind(lambda v: (
                delay(lambda: v + 1)
                .bind(lambda vn: pure(vn).bind(lambda _: delay(lambda: raiser(-10))))
            ))
            .ensure(delay(increase))
        )
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 2)

        eff = delay(lambda: raiser(-10)).catch_bind(TypeError, lambda _: pure(1).ensure(delay(increase)))
        self.assertEqual(run(eff), 1)
        self.assertEqual(glb, 3)

    def test_ensure_with_errors(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        def additional_raiser(a: int):
            if a < 0:
                raise ValueError("test ensure raise")
            return None

        glb = 0

        def increase():
            nonlocal glb
            glb += 1

        eff = delay(lambda: raiser(-10)).ensure(delay(lambda: additional_raiser(-10))).catch_fmap(ValueError, lambda _: 0)
        self.assertEqual(run(eff), 0)

        eff = (
            delay(lambda: raiser(-10))
            .ensure(delay(lambda: additional_raiser(-10)))
            .ensure(delay(increase))
            .catch_fmap(ValueError, lambda _: 0)
            .fmap(lambda v: v + 1)
        )        
        self.assertEqual(run(eff), 1)
        self.assertEqual(glb, 1)

        eff = delay(lambda: raiser(-10)).ensure(
            delay(lambda: additional_raiser(-10)).catch_fmap(ValueError, lambda _: None)
        )        
        with self.assertRaises(TypeError):
            run(eff)

    def test_contract_violation(self):
        eff = delay(lambda: 0).bind(lambda v: v + 1)  # type: ignore # noqa
        with self.assertRaises(MonadError):
            run(eff)  # type: ignore # noqa

    def test_run_safe(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = pure(0)
        res = run_safe(eff)
        self.assertIsInstance(res, Success)
        res = res.value if isinstance(res, Success) else -1
        self.assertEqual(res, 0)

        eff = delay(lambda: raiser(-10)).fmap(lambda v: v + 1)
        res = run_safe(eff)
        self.assertIsInstance(res, Fail)
        res = res.error if isinstance(res, Fail) else -1
        self.assertIsInstance(res, TypeError)

        eff = delay(lambda: raiser(-10)).catch_fmap(TypeError, lambda _: 0).fmap(lambda v: v + 1)
        res = run_safe(eff)
        self.assertIsInstance(res, Success)
        res = res.value if isinstance(res, Success) else -1
        self.assertEqual(res, 1)

    def test_retry_default_init(self):
        eff = retry(lambda: 0)
        self.assertEqual(run(eff), 0)

    def test_retry_bad_parameters(self):
        async def test(a: int):
            return a

        with self.assertRaises(ValidationError):
            _ = retry(lambda: 0, total_attempts=-2)
            _ = retry(lambda: 0, pause_seconds_between=test)  # type: ignore # noqa
            _ = retry(lambda: 0, retry_on_result=test)  # type: ignore # noqa            

        eff = retry(
            lambda: 0,
            total_attempts=2,
            retry_on_result=lambda _: True,
            pause_seconds_between=lambda v: v - 100
        )
        with self.assertRaises(RetryBadPauseError):
            run(eff)

    def test_retry_on_exception_exhausted(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = (
            pure(0)
            .fmap(lambda v: v + 1)
            .bind(lambda _: retry(lambda: raiser(-1), total_attempts=2, retry_on_exceptions=(TypeError,)))
        )
        with self.assertRaises(RetryByExceptionError):
            run(eff)

        res = run_safe(eff)
        self.assertIsInstance(res, Fail)
        err = res.error if isinstance(res, Fail) else 0
        self.assertIsInstance(err, RetryByExceptionError)
        exc = err.exception if isinstance(err, RetryByExceptionError) else 0
        self.assertIsInstance(exc, TypeError)
        previous_result = err.previous_result if isinstance(err, RetryByExceptionError) else 0
        self.assertEqual(previous_result, 1)
        previous_result_is_assigned = err.previous_result_is_assigned if isinstance(err, RetryByExceptionError) else 0
        self.assertEqual(previous_result_is_assigned, True)

    def test_retry_on_predicate_exhausted(self):
        eff = (
            pure(0)
            .fmap(lambda v: v + 1)
            .bind(lambda v: retry(lambda: v + 1, total_attempts=2, retry_on_result=lambda _: True))
        )
        with self.assertRaises(RetryByValueError):
            run(eff)

        res = run_safe(eff)
        self.assertIsInstance(res, Fail)
        err = res.error if isinstance(res, Fail) else 0
        self.assertIsInstance(err, RetryByValueError)
        previous_result = err.previous_result if isinstance(err, RetryByValueError) else 0
        self.assertEqual(previous_result, 1)
        previous_result_is_assigned = err.previous_result_is_assigned if isinstance(err, RetryByValueError) else 0
        self.assertEqual(previous_result_is_assigned, True)
        current_result = err.current_result if isinstance(err, RetryByValueError) else 0
        self.assertEqual(current_result, 2)

    def test_retry_on_exception_step_over(self):
        glb = 0

        def effect(value: int):
            def effect_inner():
                nonlocal glb
                glb += 1
                if glb < 3:
                    raise TypeError("test")
                return value
            return effect_inner

        eff = (
            pure(0)
            .fmap(lambda v: v + 1)
            .bind(lambda v: retry(effect(v), total_attempts=3, retry_on_exceptions=(TypeError,)))
        )
        self.assertEqual(run(eff), 1)

    def test_retry_on_predicate_step_over(self):
        def effect(value: int):
            def effect_inner():
                nonlocal value
                value += 1
                return value
            return effect_inner

        eff = (
            pure(0)
            .bind(lambda v: retry(effect(v), total_attempts=3, retry_on_result=lambda n: n < 3))
        )
        self.assertEqual(run(eff), 3)

    def test_transformer_pure_chains(self):
        eff = lift_pure(0).fmap(lambda x: x + 1).fmap(lambda x: x + 1)
        res = run(eff)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value if isinstance(res, Success) else 0, 2)

        res = run_safe(eff)
        self.assertTrue(isinstance(res, Success))
        res_inner = res.value if isinstance(res, Success) else 0
        self.assertTrue(isinstance(res_inner, Success))
        value = res_inner.value if isinstance(res_inner, Success) else 0
        self.assertEqual(value, 2)

        eff = lift_pure(0).fmap_result(lambda x: Success(x + 1)).fmap(lambda x: x + 1)
        res = run(eff)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value if isinstance(res, Success) else 0, 2)

        res = run_safe(eff)
        self.assertTrue(isinstance(res, Success))
        res_inner = res.value if isinstance(res, Success) else 0
        self.assertTrue(isinstance(res_inner, Success))
        value = res_inner.value if isinstance(res_inner, Success) else 0
        self.assertEqual(value, 2)

    def test_transformer_bind_chains(self):
        eff = lift_pure(0).fmap(lambda x: x + 1).bind(lambda x: lift_result(Success(x + 1)))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, 2)

        res = run_safe(eff)
        self.assertTrue(isinstance(res, Success))
        res_inner = res.value if isinstance(res, Success) else 0
        self.assertTrue(isinstance(res_inner, Success))
        value = res_inner.value if isinstance(res_inner, Success) else 0
        self.assertEqual(value, 2)

    def test_transformer_inner_error(self):
        eff = lift_error(0).fmap(lambda x: x + 1).fmap(lambda x: x + 1)
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

        res = run_safe(eff)
        self.assertTrue(isinstance(res, Success))
        res_inner = res.value if isinstance(res, Success) else 100
        self.assertTrue(isinstance(res_inner, Fail))
        value = res_inner.error if isinstance(res_inner, Fail) else 100
        self.assertEqual(value, 0)

        eff = (
            lift_result((lambda x: Fail(x) if x < 0 else Success(x))(0))
            .fmap_result(lambda x: Fail(x + 1) if x == 0 else Success(x))
            .fmap(lambda x: x + 1)
        )
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 1)

        res = run_safe(eff)
        self.assertTrue(isinstance(res, Success))
        res_inner = res.value if isinstance(res, Success) else 100
        self.assertTrue(isinstance(res_inner, Fail))
        value = res_inner.error if isinstance(res_inner, Fail) else 100
        self.assertEqual(value, 1)

    def test_transformer_lift_effect(self):
        eff = pure(0).fmap(lambda x: x + 1).bind(lambda x: delay(lambda: x + 1))
        t_eff = lift_effect(eff)
        res = run(t_eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, 2)

        res = run_safe(t_eff)
        self.assertTrue(isinstance(res, Success))
        res_inner = res.value if isinstance(res, Success) else 0
        self.assertTrue(isinstance(res_inner, Success))
        value = res_inner.value if isinstance(res_inner, Success) else 0
        self.assertEqual(value, 2)

    def test_transformer_nested_retry(self):
        g = 0

        def raiser():
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return success(None)

        def inner_second_chain(val: int):
            return retry_t(raiser, total_attempts=3, retry_on_exceptions=(TypeError,)).fmap(lambda _: val + 1)

        def inner_first_chain(val: int):
            return (
                delay_t(lambda: success(val ** 2))
                .bind(inner_second_chain)
            )

        eff = lift_pure(5).fmap(lambda v: v + 5).bind(inner_first_chain)
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, 101)

    def test_stack_safety(self):
        eff = pure(0)
        for _ in range(10_000):
            eff = eff.bind(lambda v: pure(v + 1))
        self.assertEqual(run(eff), 10_000)

    def test_lift2(self):
        def two(a: int, b: int):
            return [a, b]

        eff = lift2(two, pure(0), pure(1))
        self.assertEqual(run(eff), [0, 1])

        eff = lift2(two, pure(0), delay(lambda: 1))
        self.assertEqual(run(eff), [0, 1])

        eff = lift2(two, pure(0), retry(lambda: 1))
        self.assertEqual(run(eff), [0, 1])

        eff = lift2(two, delay(lambda: 0), retry(lambda: 1))
        self.assertEqual(run(eff), [0, 1])

    def test_lift3(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        eff = lift3(three, pure(0), delay(lambda: 1), retry(lambda: 2))
        self.assertEqual(run(eff), [0, 1, 2])

    def test_lift4(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]

        eff = lift4(four, pure(0), delay(lambda: 1), retry(lambda: 2), pure(3))
        self.assertEqual(run(eff), [0, 1, 2, 3])

    def test_lift2_transformer(self):
        def two(a: int, b: int):
            return [a, b]

        eff = lift2_t(two, lift_pure(0), lift_pure(1))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1])

        eff = lift2_t(two, lift_error(0), lift_pure(1))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

        eff = lift2_t(two, lift_pure(0), lift_error(1))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 1)

        eff = lift2_t(two, delay_t(lambda: success(0)), lift_result(success(1)))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1])

        eff = lift2_t(two, delay_t(lambda: fail(0)), lift_result(success(1)))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

    def test_lift3_transformer(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        eff = lift3_t(three, lift_pure(0), lift_pure(1), lift_pure(2))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1, 2])        

        eff = lift3_t(three, lift_error(0), lift_pure(1), lift_pure(2))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

        eff = lift3_t(three, lift_pure(0), lift_pure(1), lift_error(2))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 2)

        eff = lift3_t(three, delay_t(lambda: success(0)), lift_result(success(1)), lift_effect(pure(2)))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1, 2])

        eff = lift3_t(three, delay_t(lambda: fail(0)), lift_result(success(1)), lift_effect(pure(2)))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

    def test_lift4_transformer(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]

        eff = lift4_t(four, lift_pure(0), lift_pure(1), lift_pure(2), lift_pure(3))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1, 2, 3])

        eff = lift4_t(four, lift_error(0), lift_pure(1), lift_pure(2), lift_pure(3))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

        eff = lift4_t(four, lift_pure(0), lift_pure(1), lift_pure(2), lift_error(3))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 3)

        eff = lift4_t(four, delay_t(lambda: success(0)), lift_result(success(1)), lift_effect(pure(2)), lift_effect(pure(3)))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1, 2, 3])

        eff = lift4_t(four, delay_t(lambda: fail(0)), lift_result(success(1)), lift_effect(pure(2)), lift_effect(pure(3)))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)


if __name__ == '__main__':
    unittest.main()

import unittest

from mafunca.common.exceptions import MonadError
from mafunca.common.exceptions import ValidationError, RetryBadPauseError, RetryByExceptionError, RetryByValueError
from mafunca.result import Ok, Err
from mafunca.effect_sync import pure, delay, retry
from mafunca.effect_sync import lift2, lift3, lift4
from mafunca.effect_sync_transformer import pure as lift_pure, lift_error
from mafunca.effect_sync_transformer import delay as delay_t, retry as retry_t
from mafunca.effect_sync_transformer import lift_effect, lift_result
from mafunca.effect_sync_transformer import lift2 as lift2_t, lift3 as lift3_t, lift4 as lift4_t
from mafunca.effect_runners import run, run_safe


class TestEffectSync(unittest.TestCase):
    def test_init(self):
        eff = pure(0)
        self.assertEqual(run(eff), 0)

        eff = delay(lambda: 0)
        self.assertEqual(run(eff), 0)

    def test_map(self):
        eff = pure(0).map(lambda v: v + 1).map(lambda v: v + 1)
        self.assertEqual(run(eff), 2)

        eff = delay(lambda: 0).map(lambda v: v + 1).map(lambda v: v + 1)
        self.assertEqual(run(eff), 2)

    def test_bind(self):
        eff = pure(0).bind(lambda v: pure(v + 1)).map(lambda v: v + 1)
        self.assertEqual(run(eff), 2)

        eff = pure(0).bind(lambda v: delay(lambda: v + 1).map(lambda vn: vn + 1))
        self.assertEqual(run(eff), 2)

        eff = delay(lambda: 0).bind(lambda v: pure(v + 1)).map(lambda v: v + 1)
        self.assertEqual(run(eff), 2)

        eff = delay(lambda: 0).bind(lambda v: delay(lambda: v + 1).map(lambda vn: vn + 1))
        self.assertEqual(run(eff), 2)

        eff = (
            delay(lambda: 0)
            .bind(lambda v: delay(lambda: v + 1).bind(lambda vn: pure(vn + 1)))
        )
        self.assertEqual(run(eff), 2)

    def test_catch(self):
        def raiser():
            raise TypeError("test raise")

        eff = delay(raiser).catch_map(TypeError, lambda _: 0).map(lambda v: v + 1)
        self.assertEqual(run(eff), 1)

        eff = delay(raiser).map(lambda v: v + 1).catch_map(TypeError, lambda _: 0)
        self.assertEqual(run(eff), 0)

        eff = delay(raiser).catch_bind(TypeError, lambda _: pure(0)).map(lambda v: v + 1)
        self.assertEqual(run(eff), 1)

        eff = (
            delay(raiser)
            .bind(lambda v: delay(lambda: v + 1))
            .catch_bind(TypeError, lambda _: pure(0).bind(lambda v: pure(v + 1)))
            .map(lambda v: v + 1)
        )
        self.assertEqual(run(eff), 2)

    def test_catch_no_effect_by_exception_type(self):
        def raiser():
            raise TypeError("test raise")

        eff = delay(raiser).catch_map(ValueError, lambda _: 0)
        with self.assertRaises(TypeError):
            run(eff)

    def test_catch_no_effect_by_scope(self):
        def raiser():
            raise TypeError("test raise")

        eff = delay(raiser).bind(lambda v: pure(v + 1).catch_map(TypeError, lambda _: 0))
        with self.assertRaises(TypeError):
            run(eff)

    def test_catch_no_effect_with_no_errors(self):
        eff = pure(0).bind(lambda v: pure(v + 1)).catch_map(TypeError, lambda _: 0)
        self.assertEqual(run(eff), 1)

        eff = pure(0).map(lambda v: v + 1).catch_bind(TypeError, lambda _: pure(0))
        self.assertEqual(run(eff), 1)

    def test_catch_with_error_in_cather(self):
        def raiser():
            raise TypeError("test raise")

        def catcher_raiser():
            raise ValueError("test catcher raise")

        eff = delay(raiser).catch_bind(TypeError, lambda _: delay(catcher_raiser))
        with self.assertRaises(ValueError):
            run(eff)

    def test_ensure(self):
        def raiser():
            raise TypeError("test raise")

        glb = 0

        def increase():
            nonlocal glb
            glb += 1

        eff = delay(lambda: 0).map(lambda v: v + 1).ensure(delay(increase))
        res = run(eff)
        self.assertEqual(res, 1)
        self.assertEqual(glb, 1)

        eff = delay(raiser).map(lambda v: v + 1).ensure(delay(increase))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 2)

        eff = delay(raiser).ensure(delay(increase)).ensure(delay(increase))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 4)

        eff = delay(raiser).ensure(delay(increase).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 6)

        eff = pure(0).ensure(delay(increase))
        run(eff)
        self.assertEqual(glb, 7)

    def test_ensure_scopes(self):
        def raiser():
            raise TypeError("test raise")

        glb = 0

        def increase():
            nonlocal glb
            glb += 1

        eff = delay(raiser).bind(lambda v: pure(v + 1).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 0)

        eff = pure(0).bind(lambda _: delay(raiser).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 1)

        eff = (
            pure(0)
            .bind(lambda v: (
                delay(lambda: v + 1)
                .bind(lambda vn: pure(vn).bind(lambda _: delay(raiser)))
            ))
            .ensure(delay(increase))
        )
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 2)

        eff = delay(raiser).catch_bind(TypeError, lambda _: pure(1).ensure(delay(increase)))
        self.assertEqual(run(eff), 1)
        self.assertEqual(glb, 3)

    def test_ensure_with_errors(self):
        def raiser():
            raise TypeError("test raise")

        def additional_raiser():
            raise ValueError("test ensure raise")

        glb = 0

        def increase():
            nonlocal glb
            glb += 1

        eff = delay(raiser).ensure(delay(additional_raiser)).catch_map(ValueError, lambda _: 0)
        self.assertEqual(run(eff), 0)

        eff = (
            delay(raiser)
            .ensure(delay(additional_raiser))
            .ensure(delay(increase))
            .catch_map(ValueError, lambda _: 0)
            .map(lambda v: v + 1)
        )
        self.assertEqual(run(eff), 1)
        self.assertEqual(glb, 1)

        eff = delay(raiser).ensure(
            delay(additional_raiser).catch_map(ValueError, lambda _: None)
        )
        with self.assertRaises(TypeError):
            run(eff)

    def test_contract_violation(self):
        eff = delay(lambda: 0).bind(lambda v: v + 1)
        with self.assertRaises(MonadError):
            run(eff)

    def test_run_safe(self):
        def raiser():
            raise TypeError("test raise")

        eff = pure(0)
        res = run_safe(eff)
        self.assertIsInstance(res, Ok)
        self.assertEqual(res.value, 0)

        eff = delay(raiser).map(lambda v: v + 1)
        res = run_safe(eff)
        self.assertIsInstance(res, Err)
        self.assertIsInstance(res.error, TypeError)

        eff = delay(raiser).catch_map(TypeError, lambda _: 0).map(lambda v: v + 1)
        res = run_safe(eff)
        self.assertIsInstance(res, Ok)
        self.assertEqual(res.value, 1)

    def test_retry_default_init(self):
        eff = retry(lambda: 0)
        self.assertEqual(run(eff), 0)

    def test_retry_bad_parameters(self):
        async def test(a: int):
            return a

        with self.assertRaises(ValidationError):
            _ = retry(lambda: 0, total_attempts=-2)
            _ = retry(lambda: 0, pause_seconds_between=test)  # noqa
            _ = retry(lambda: 0, retry_on_result=test)  # noqa
            _ = retry(lambda: 0, retry_on_exceptions=("err",))  # noqa

        eff = retry(
            lambda: 0,
            total_attempts=2,
            retry_on_result=lambda _: True,
            pause_seconds_between=lambda v: v - 100
        )
        with self.assertRaises(RetryBadPauseError):
            run(eff)

    def test_retry_on_exception_exhausted(self):
        def raiser():
            raise TypeError("test raise")

        eff = (
            pure(0)
            .map(lambda v: v + 1)
            .bind(lambda _: retry(raiser, total_attempts=2, retry_on_exceptions=(TypeError,)))
        )
        with self.assertRaises(RetryByExceptionError):
            run(eff)

        res = run_safe(eff)
        self.assertIsInstance(res, Err)
        err = res.error
        self.assertIsInstance(err, RetryByExceptionError)
        self.assertIsInstance(err.exception, TypeError)
        self.assertEqual(err.previous_result, 1)
        self.assertEqual(err.previous_result_is_assigned, True)

    def test_retry_on_predicate_exhausted(self):
        eff = (
            pure(0)
            .map(lambda v: v + 1)
            .bind(lambda v: retry(lambda: v + 1, total_attempts=2, retry_on_result=lambda _: True))
        )
        with self.assertRaises(RetryByValueError):
            run(eff)

        res = run_safe(eff)
        self.assertIsInstance(res, Err)
        err = res.error
        self.assertIsInstance(err, RetryByValueError)
        self.assertEqual(err.previous_result, 1)
        self.assertEqual(err.previous_result_is_assigned, True)
        self.assertEqual(err.current_result, 2)

    def test_retry_on_exception_step_over(self):
        glb = 0

        def effect(value):
            def effect_inner():
                nonlocal glb
                glb += 1
                if glb < 3:
                    raise TypeError("test")
                return value
            return effect_inner

        eff = (
            pure(0)
            .map(lambda v: v + 1)
            .bind(lambda v: retry(effect(v), total_attempts=3, retry_on_exceptions=(TypeError,)))
        )
        self.assertEqual(run(eff), 1)

    def test_retry_on_predicate_step_over(self):
        def effect(value):
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
        eff = lift_pure(0).map(lambda x: x + 1).map(lambda x: x + 1)
        self.assertEqual(run(eff).value, 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

        eff = lift_pure(0).map_result(lambda x: Ok(x + 1)).map(lambda x: x + 1)
        self.assertEqual(run(eff).value, 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

    def test_transformer_bind_chains(self):
        eff = lift_pure(0).map(lambda x: x + 1).bind(lambda x: lift_result(Ok(x + 1)))
        self.assertEqual(run(eff).value, 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

    def test_transformer_inner_error(self):
        eff = lift_error(0).map(lambda x: x + 1).map(lambda x: x + 1)
        self.assertTrue(run(eff).is_error)
        self.assertEqual(run(eff).error, 0)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_error)
        self.assertEqual(res.value.error, 0)

        eff = lift_pure(0).map_result(lambda x: Err(x + 1)).map(lambda x: x + 1)
        self.assertTrue(run(eff).is_error)
        self.assertEqual(run(eff).error, 1)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_error)
        self.assertEqual(res.value.error, 1)

    def test_transformer_lift_effect(self):
        eff = pure(0).map(lambda x: x + 1).bind(lambda x: delay(lambda: x + 1))
        t_eff = lift_effect(eff)
        self.assertTrue(run(t_eff).is_ok)
        self.assertEqual(run(t_eff).value, 2)

        res = run_safe(t_eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

    def test_transformer_nested_retry(self):
        g = 0

        def raiser():
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return Ok(None)

        def inner_second_chain(val: int):
            return retry_t(raiser, total_attempts=3, retry_on_exceptions=(TypeError,)).map(lambda _: val + 1)

        def inner_first_chain(val: int):
            return (
                delay_t(lambda: Ok(val ** 2))
                .bind(inner_second_chain)
            )

        eff = lift_pure(5).map(lambda v: v + 5).bind(inner_first_chain)
        self.assertEqual(run(eff).value, 101)

    def test_stack_safety(self):
        eff = pure(0)
        for _ in range(10_000):
            eff = eff.bind(lambda v: pure(v + 1))
        self.assertEqual(run(eff), 10_000)

    def test_lift2(self):
        def two(a, b):
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
        def three(a, b, c):
            return [a, b, c]

        eff = lift3(three, pure(0), delay(lambda: 1), retry(lambda: 2))
        self.assertEqual(run(eff), [0, 1, 2])

    def test_lift4(self):
        def four(a, b, c, d):
            return [a, b, c, d]

        eff = lift4(four, pure(0), delay(lambda: 1), retry(lambda: 2), pure(3))
        self.assertEqual(run(eff), [0, 1, 2, 3])

    def test_lift2_transformer(self):
        def two(a, b):
            return [a, b]

        eff = lift2_t(two, lift_pure(0), lift_pure(1))
        self.assertEqual(run(eff).value, [0, 1])

        eff = lift2_t(two, lift_error(0), lift_pure(1))
        res = run(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

        eff = lift2_t(two, lift_pure(0), lift_error(1))
        res = run(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 1)

        eff = lift2_t(two, delay_t(lambda: Ok(0)), lift_result(Ok(1)))
        self.assertEqual(run(eff).value, [0, 1])

        eff = lift2_t(two, delay_t(lambda: Err(0)), lift_result(Ok(1)))
        res = run(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

    def test_lift3_transformer(self):
        def three(a, b, c):
            return [a, b, c]

        eff = lift3_t(three, lift_pure(0), lift_pure(1), lift_pure(2))
        self.assertEqual(run(eff).value, [0, 1, 2])

        eff = lift3_t(three, lift_error(0), lift_pure(1), lift_pure(2))
        res = run(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

        eff = lift3_t(three, lift_pure(0), lift_pure(1), lift_error(2))
        res = run(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 2)

        eff = lift3_t(three, delay_t(lambda: Ok(0)), lift_result(Ok(1)), lift_effect(pure(2)))
        self.assertEqual(run(eff).value, [0, 1, 2])

        eff = lift3_t(three, delay_t(lambda: Err(0)), lift_result(Ok(1)), lift_effect(pure(2)))
        res = run(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

    def test_lift4_transformer(self):
        def four(a, b, c, d):
            return [a, b, c, d]

        eff = lift4_t(four, lift_pure(0), lift_pure(1), lift_pure(2), lift_pure(3))
        self.assertEqual(run(eff).value, [0, 1, 2, 3])

        eff = lift4_t(four, lift_error(0), lift_pure(1), lift_pure(2), lift_pure(3))
        res = run(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

        eff = lift4_t(four, lift_pure(0), lift_pure(1), lift_pure(2), lift_error(3))
        res = run(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 3)

        eff = lift4_t(four, delay_t(lambda: Ok(0)), lift_result(Ok(1)), lift_effect(pure(2)), lift_effect(pure(3)))
        self.assertEqual(run(eff).value, [0, 1, 2, 3])

        eff = lift4_t(four, delay_t(lambda: Err(0)), lift_result(Ok(1)), lift_effect(pure(2)), lift_effect(pure(3)))
        res = run(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)


if __name__ == '__main__':
    unittest.main()

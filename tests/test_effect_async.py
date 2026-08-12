import unittest
import asyncio

from mafunca.common.exceptions import MonadError
from mafunca.common.exceptions import ValidationError, RetryBadPauseError, RetryByExceptionError, RetryByValueError
from mafunca.result import Ok, Err
from mafunca.effect_async import pure, delay, retry
from mafunca.effect_async import lift2, lift3, lift4
from mafunca.effect_async_transformer import pure as pure_t, lift_error as error_t
from mafunca.effect_async_transformer import delay as delay_t, retry as retry_t
from mafunca.effect_async_transformer import lift_effect, lift_result
from mafunca.effect_async_transformer import lift2 as lift2_t, lift3 as lift3_t, lift4 as lift4_t
from mafunca.effect_runners import run_async, run_safe_async


class TestEffectAsync(unittest.IsolatedAsyncioTestCase):
    async def test_init(self):
        async def zero():
            return 0

        eff = pure(0)
        self.assertEqual(await run_async(eff), 0)

        eff = delay(zero)
        self.assertEqual(await run_async(eff), 0)

    async def test_map(self):
        async def zero():
            return 0
        
        eff = pure(0).map(lambda v: v + 1).map(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 2)

        eff = delay(zero).map(lambda v: v + 1).map(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 2)

    async def test_bind(self):
        async def zero():
            return 0

        def plus_one(v):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = pure(0).bind(lambda v: pure(v + 1)).map(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 2)

        eff = pure(0).bind(lambda v: delay(plus_one(v)).map(lambda vn: vn + 1))
        self.assertEqual(await run_async(eff), 2)

        eff = delay(zero).bind(lambda v: pure(v + 1)).map(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 2)

        eff = delay(zero).bind(lambda v: delay(plus_one(v)).map(lambda vn: vn + 1))
        self.assertEqual(await run_async(eff), 2)

        eff = (
            delay(zero)
            .bind(lambda v: delay(plus_one(v)).bind(lambda vn: pure(vn + 1)))
        )
        self.assertEqual(await run_async(eff), 2)

    async def test_catch(self):
        async def raiser():
            raise TypeError("test raise")

        def plus_one(v):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = delay(raiser).catch_map(TypeError, lambda _: 0).map(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 1)

        eff = delay(raiser).map(lambda v: v + 1).catch_map(TypeError, lambda _: 0)
        self.assertEqual(await run_async(eff), 0)

        eff = delay(raiser).catch_bind(TypeError, lambda _: pure(0)).map(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 1)

        eff = (
            delay(raiser)
            .bind(lambda v: delay(plus_one(v)))
            .catch_bind(TypeError, lambda _: pure(0).bind(lambda v: pure(v + 1)))
            .map(lambda v: v + 1)
        )
        self.assertEqual(await run_async(eff), 2)

    async def test_catch_no_effect_by_exception_type(self):
        async def raiser():
            raise TypeError("test raise")

        eff = delay(raiser).catch_map(ValueError, lambda _: 0)
        with self.assertRaises(TypeError):
            await run_async(eff)

    async def test_catch_no_effect_by_scope(self):
        async def raiser():
            raise TypeError("test raise")

        eff = delay(raiser).bind(lambda v: pure(v + 1).catch_map(TypeError, lambda _: 0))
        with self.assertRaises(TypeError):
            await run_async(eff)

    async def test_catch_no_effect_with_no_errors(self):
        eff = pure(0).bind(lambda v: pure(v + 1)).catch_map(TypeError, lambda _: 0)
        self.assertEqual(await run_async(eff), 1)

        eff = pure(0).map(lambda v: v + 1).catch_bind(TypeError, lambda _: pure(0))
        self.assertEqual(await run_async(eff), 1)

    async def test_catch_with_error_in_cather(self):
        async def raiser():
            raise TypeError("test raise")

        async def catcher_raiser():
            raise ValueError("test catcher raise")

        eff = delay(raiser).catch_bind(TypeError, lambda _: delay(catcher_raiser))
        with self.assertRaises(ValueError):
            await run_async(eff)

    async def test_ensure(self):
        async def raiser():
            raise TypeError("test raise")

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = pure(0).map(lambda v: v + 1).ensure(delay(increase))
        res = await run_async(eff)
        self.assertEqual(res, 1)
        self.assertEqual(glb, 1)

        eff = delay(raiser).map(lambda v: v + 1).ensure(delay(increase))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 2)

        eff = delay(raiser).ensure(delay(increase)).ensure(delay(increase))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 4)

        eff = delay(raiser).ensure(delay(increase).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 6)

        eff = pure(0).ensure(delay(increase))
        await run_async(eff)
        self.assertEqual(glb, 7)

    async def test_ensure_scopes(self):
        async def raiser():
            raise TypeError("test raise")

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        def plus_one(v):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = delay(raiser).bind(lambda v: pure(v + 1).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 0)

        eff = pure(0).bind(lambda _: delay(raiser).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 1)

        eff = (
            pure(0)
            .bind(lambda v: (
                delay(plus_one(v))
                .bind(lambda vn: pure(vn).bind(lambda _: delay(raiser)))
            ))
            .ensure(delay(increase))
        )
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 2)

        eff = delay(raiser).catch_bind(TypeError, lambda _: pure(1).ensure(delay(increase)))
        self.assertEqual(await run_async(eff), 1)
        self.assertEqual(glb, 3)

    async def test_ensure_with_errors(self):
        async def raiser():
            raise TypeError("test raise")

        async def additional_raiser():
            raise ValueError("test ensure raise")

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = delay(raiser).ensure(delay(additional_raiser)).catch_map(ValueError, lambda _: 0)
        self.assertEqual(await run_async(eff), 0)

        eff = (
            delay(raiser)
            .ensure(delay(additional_raiser))
            .ensure(delay(increase))
            .catch_map(ValueError, lambda _: 0)
            .map(lambda v: v + 1)
        )
        self.assertEqual(await run_async(eff), 1)
        self.assertEqual(glb, 1)

        eff = delay(raiser).ensure(
            delay(additional_raiser).catch_map(ValueError, lambda _: None)
        )
        with self.assertRaises(TypeError):
            await run_async(eff)

    async def test_ensure_runs_on_cancelled_error(self):
        async def cancelled():
            raise asyncio.CancelledError()

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = delay(cancelled).ensure(delay(increase))
        with self.assertRaises(asyncio.CancelledError):
            await run_async(eff)
        self.assertEqual(glb, 1)

    async def test_contract_violation(self):
        eff = pure(0).bind(lambda v: v + 1)
        with self.assertRaises(MonadError):
            await run_async(eff)

    async def test_run_safe(self):
        async def raiser():
            raise TypeError("test raise")

        eff = pure(0)
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Ok)
        self.assertEqual(res.value, 0)

        eff = delay(raiser).map(lambda v: v + 1)
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Err)
        self.assertIsInstance(res.error, TypeError)

        eff = delay(raiser).catch_map(TypeError, lambda _: 0).map(lambda v: v + 1)
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Ok)
        self.assertEqual(res.value, 1)

    async def test_retry_default_init(self):
        async def zero():
            return 0

        eff = retry(zero)
        self.assertEqual(await run_async(eff), 0)

    async def test_retry_bad_parameters(self):
        async def zero():
            return 0

        async def test(a: int):
            return a

        with self.assertRaises(ValidationError):
            _ = retry(zero, total_attempts=-2)
            _ = retry(zero, pause_seconds_between=test)  # noqa
            _ = retry(zero, retry_on_result=test)  # noqa
            _ = retry(zero, retry_on_exceptions=("err",))  # noqa

        eff = retry(
            zero,
            total_attempts=2,
            retry_on_result=lambda _: True,
            pause_seconds_between=lambda v: v - 100
        )
        with self.assertRaises(RetryBadPauseError):
            await run_async(eff)

    async def test_retry_on_exception_exhausted(self):
        async def raiser():
            raise TypeError("test raise")

        eff = (
            pure(0)
            .map(lambda v: v + 1)
            .bind(lambda _: retry(raiser, total_attempts=2, retry_on_exceptions=(TypeError,)))
        )
        with self.assertRaises(RetryByExceptionError):
            await run_async(eff)

        res = await run_safe_async(eff)
        self.assertIsInstance(res, Err)
        err = res.error
        self.assertIsInstance(err, RetryByExceptionError)
        self.assertIsInstance(err.exception, TypeError)
        self.assertEqual(err.previous_result, 1)
        self.assertEqual(err.previous_result_is_assigned, True)

    async def test_retry_on_predicate_exhausted(self):
        def plus_one(v):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = (
            pure(0)
            .map(lambda v: v + 1)
            .bind(lambda v: retry(plus_one(v), total_attempts=2, retry_on_result=lambda _: True))
        )
        with self.assertRaises(RetryByValueError):
            await run_async(eff)

        res = await run_safe_async(eff)
        self.assertIsInstance(res, Err)
        err = res.error
        self.assertIsInstance(err, RetryByValueError)
        self.assertEqual(err.previous_result, 1)
        self.assertEqual(err.previous_result_is_assigned, True)
        self.assertEqual(err.current_result, 2)

    async def test_retry_on_exception_step_over(self):
        glb = 0

        def effect(value):
            async def effect_inner():
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
        self.assertEqual(await run_async(eff), 1)

    async def test_retry_on_predicate_step_over(self):
        def effect(value):
            async def effect_inner():
                nonlocal value
                value += 1
                return value
            return effect_inner

        eff = (
            pure(0)
            .bind(lambda v: retry(effect(v), total_attempts=3, retry_on_result=lambda n: n < 3))
        )
        self.assertEqual(await run_async(eff), 3)

    async def test_transformer_pure_chains(self):
        eff = pure_t(0).map(lambda x: x + 1).map(lambda x: x + 1)
        self.assertEqual((await run_async(eff)).value, 2)

        res = await run_safe_async(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

        eff = pure_t(0).map_result(lambda x: Ok(x + 1)).map(lambda x: x + 1)
        self.assertEqual((await run_async(eff)).value, 2)

        res = await run_safe_async(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

    async def test_transformer_bind_chains(self):
        eff = pure_t(0).map(lambda x: x + 1).bind(lambda x: lift_result(Ok(x + 1)))
        self.assertEqual((await run_async(eff)).value, 2)

        res = await run_safe_async(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

    async def test_transformer_inner_error(self):
        eff = error_t(0).map(lambda x: x + 1).map(lambda x: x + 1)
        self.assertTrue((await run_async(eff)).is_error)
        self.assertEqual((await run_async(eff)).error, 0)

        res = await run_safe_async(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_error)
        self.assertEqual(res.value.error, 0)

        eff = pure_t(0).map_result(lambda x: Err(x + 1)).map(lambda x: x + 1)
        self.assertTrue((await run_async(eff)).is_error)
        self.assertEqual((await run_async(eff)).error, 1)

        res = await run_safe_async(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_error)
        self.assertEqual(res.value.error, 1)

    async def test_transformer_lift_effect(self):
        def plus_one(v):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = pure(0).map(lambda x: x + 1).bind(lambda x: delay(plus_one(x)))
        t_eff = lift_effect(eff)
        self.assertTrue((await run_async(t_eff)).is_ok)
        self.assertEqual((await run_async(t_eff)).value, 2)

        res = await run_safe_async(t_eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

    async def test_transformer_nested_retry(self):
        g = 0

        async def raiser():
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return Ok(None)

        def square(val):
            async def square_inner():
                return Ok(val ** 2)
            return square_inner

        def inner_second_chain(val: int):
            return retry_t(raiser, total_attempts=3, retry_on_exceptions=(TypeError,)).map(lambda _: val + 1)

        def inner_first_chain(val: int):
            return (
                delay_t(square(val))
                .bind(inner_second_chain)
            )

        eff = pure_t(5).map(lambda v: v + 5).bind(inner_first_chain)
        self.assertEqual((await run_async(eff)).value, 101)

    async def test_timeout(self):
        async def zero():
            await asyncio.sleep(0.2)
            return 0

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = delay(zero, wait_seconds=0.1)
        with self.assertRaises(TimeoutError):
            await run_async(eff)

        res = await run_safe_async(eff)
        self.assertIsInstance(res, Err)
        self.assertIsInstance(res.error, TimeoutError)

        eff = delay(zero, wait_seconds=0.1).catch_map(TimeoutError, lambda _: 1)
        res = await run_async(eff)
        self.assertEqual(res, 1)

        eff = delay(zero, wait_seconds=0.1).ensure(delay(increase))
        with self.assertRaises(TimeoutError):
            await run_async(eff)
        self.assertEqual(glb, 1)

    async def test_stack_safety(self):
        eff = pure(0)
        for _ in range(10_000):
            eff = eff.bind(lambda v: pure(v + 1))
        self.assertEqual(await run_async(eff), 10_000)

    async def test_cancelled_error_not_catch(self):

        async def cancelled():
            raise asyncio.CancelledError()

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = delay(cancelled).catch_bind(Exception, lambda _: delay(increase))
        with self.assertRaises(asyncio.CancelledError):
            await run_async(eff)
        with self.assertRaises(asyncio.CancelledError):
            await run_safe_async(eff)
        self.assertEqual(glb, 0)

    async def test_cancelled_error_catch_intentionally(self):

        async def cancelled():
            raise asyncio.CancelledError()

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = delay(cancelled).catch_bind(asyncio.CancelledError, lambda _: delay(increase))
        _ = await run_async(eff)
        self.assertEqual(glb, 1)
        _ = await run_safe_async(eff)
        self.assertEqual(glb, 2)

    async def test_cancelled_error_not_replaced(self):

        async def cancelled():
            raise asyncio.CancelledError()

        async def error_raiser():
            raise TypeError("Error")

        eff = delay(cancelled).ensure(delay(error_raiser))
        with self.assertRaises(asyncio.CancelledError):
            await run_async(eff)
        with self.assertRaises(asyncio.CancelledError):
            await run_safe_async(eff)

    async def test_lift2(self):
        def two(a, b):
            return [a, b]

        async def unit():
            return 1

        eff = lift2(two, pure(0), pure(1))
        self.assertEqual(await run_async(eff), [0, 1])

        eff = lift2(two, pure(0), delay(unit))
        self.assertEqual(await run_async(eff), [0, 1])

        eff = lift2(two, pure(0), retry(unit))
        self.assertEqual(await run_async(eff), [0, 1])

        eff = lift2(two, delay(unit), retry(unit))
        self.assertEqual(await run_async(eff), [1, 1])

    async def test_lift3(self):
        def three(a, b, c):
            return [a, b, c]

        async def unit():
            return 1

        eff = lift3(three, pure(1), delay(unit), retry(unit))
        self.assertEqual(await run_async(eff), [1, 1, 1])

    async def test_lift4(self):
        def four(a, b, c, d):
            return [a, b, c, d]

        async def unit():
            return 1

        eff = lift4(four, pure(0), delay(unit), retry(unit), pure(3))
        self.assertEqual(await run_async(eff), [0, 1, 1, 3])

    async def test_lift2_transformer(self):
        def two(a, b):
            return [a, b]

        async def ok():
            return Ok(0)

        async def err():
            return Err(0)

        eff = lift2_t(two, pure_t(0), pure_t(1))
        self.assertEqual((await run_async(eff)).value, [0, 1])

        eff = lift2_t(two, error_t(0), pure_t(1))
        res = await run_async(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

        eff = lift2_t(two, pure_t(0), error_t(1))
        res = await run_async(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 1)

        eff = lift2_t(two, delay_t(ok), lift_result(Ok(1)))
        self.assertEqual((await run_async(eff)).value, [0, 1])

        eff = lift2_t(two, delay_t(err), lift_result(Ok(1)))
        res = await run_async(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

    async def test_lift3_transformer(self):
        def three(a, b, c):
            return [a, b, c]

        async def ok():
            return Ok(0)

        async def err():
            return Err(0)

        eff = lift3_t(three, pure_t(0), pure_t(1), pure_t(2))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2])

        eff = lift3_t(three, error_t(0), pure_t(1), pure_t(2))
        res = await run_async(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

        eff = lift3_t(three, pure_t(0), pure_t(1), error_t(2))
        res = await run_async(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 2)

        eff = lift3_t(three, delay_t(ok), lift_result(Ok(1)), lift_effect(pure(2)))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2])

        eff = lift3_t(three, delay_t(err), lift_result(Ok(1)), lift_effect(pure(2)))
        res = await run_async(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

    async def test_lift4_transformer(self):
        def four(a, b, c, d):
            return [a, b, c, d]

        async def ok():
            return Ok(0)

        async def err():
            return Err(0)

        eff = lift4_t(four, pure_t(0), pure_t(1), pure_t(2), pure_t(3))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2, 3])

        eff = lift4_t(four, error_t(0), pure_t(1), pure_t(2), pure_t(3))
        res = await run_async(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)

        eff = lift4_t(four, pure_t(0), pure_t(1), pure_t(2), error_t(3))
        res = await run_async(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 3)

        eff = lift4_t(four, delay_t(ok), lift_result(Ok(1)), lift_effect(pure(2)), lift_effect(pure(3)))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2, 3])

        eff = lift4_t(four, delay_t(err), lift_result(Ok(1)), lift_effect(pure(2)), lift_effect(pure(3)))
        res = await run_async(eff)
        self.assertTrue(res.is_error)
        self.assertEqual(res.error, 0)


if __name__ == '__main__':
    unittest.main()

import unittest
import asyncio

from mafunca.common.exceptions import MonadError
from mafunca.common.exceptions import ValidationError, RetryBadPauseError, RetryByExceptionError, RetryByValueError
from mafunca.result import Success, Fail, success, fail
from mafunca.effect_async import pure, delay, retry
from mafunca.effect_async import lift2, lift3, lift4
from mafunca.trans_effect_async import pure_success as pure_t, pure_fail as error_t
from mafunca.trans_effect_async import delay as delay_t, retry as retry_t
from mafunca.trans_effect_async import lift_effect, pure_result as lift_result
from mafunca.trans_effect_async import lift2 as lift2_t, lift3 as lift3_t, lift4 as lift4_t
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
        
        eff = pure(0).fmap(lambda v: v + 1).fmap(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 2)

        eff = delay(zero).fmap(lambda v: v + 1).fmap(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 2)

    async def test_bind(self):
        async def zero():
            return 0

        def plus_one(v: int):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = pure(0).bind(lambda v: pure(v + 1)).fmap(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 2)

        eff = pure(0).bind(lambda v: delay(plus_one(v)).fmap(lambda vn: vn + 1))
        self.assertEqual(await run_async(eff), 2)

        eff = delay(zero).bind(lambda v: pure(v + 1)).fmap(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 2)

        eff = delay(zero).bind(lambda v: delay(plus_one(v)).fmap(lambda vn: vn + 1))
        self.assertEqual(await run_async(eff), 2)

        eff = (
            delay(zero)
            .bind(lambda v: delay(plus_one(v)).bind(lambda vn: pure(vn + 1)))
        )
        self.assertEqual(await run_async(eff), 2)

    async def test_catch(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        def plus_one(v: int):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = delay(lambda: raiser(-1)).catch_fmap(TypeError, lambda _: 0).fmap(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 1)

        eff = delay(lambda: raiser(-1)).fmap(lambda v: v + 1).catch_fmap(TypeError, lambda _: 0)
        self.assertEqual(await run_async(eff), 0)

        eff = delay(lambda: raiser(-1)).catch_bind(TypeError, lambda _: pure(0)).fmap(lambda v: v + 1)
        self.assertEqual(await run_async(eff), 1)

        eff = (
            delay(lambda: raiser(-1))
            .bind(lambda v: delay(plus_one(v)))
            .catch_bind(TypeError, lambda _: pure(0).bind(lambda v: pure(v + 1)))
            .fmap(lambda v: v + 1)
        )
        self.assertEqual(await run_async(eff), 2)

    async def test_catch_no_effect_by_exception_type(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = delay(lambda: raiser(-1)).catch_fmap(ValueError, lambda _: 0)
        with self.assertRaises(TypeError):
            await run_async(eff)

    async def test_catch_no_effect_by_scope(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = delay(lambda: raiser(-1)).bind(lambda v: pure(v + 1).catch_fmap(TypeError, lambda _: 0))
        with self.assertRaises(TypeError):
            await run_async(eff)

    async def test_catch_no_effect_with_no_errors(self):
        eff = pure(0).bind(lambda v: pure(v + 1)).catch_fmap(TypeError, lambda _: 0)
        self.assertEqual(await run_async(eff), 1)

        eff = pure(0).fmap(lambda v: v + 1).catch_bind(TypeError, lambda _: pure(0))
        self.assertEqual(await run_async(eff), 1)

    async def test_catch_with_error_in_cather(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        async def catcher_raiser(a: int):
            if a < 0:
                raise ValueError("test catcher raise")
            return a

        eff = delay(lambda: raiser(-1)).catch_bind(TypeError, lambda _: delay(lambda: catcher_raiser(-1)))
        with self.assertRaises(ValueError):
            await run_async(eff)

    async def test_ensure(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = pure(0).fmap(lambda v: v + 1).ensure(delay(increase))
        res = await run_async(eff)
        self.assertEqual(res, 1)
        self.assertEqual(glb, 1)

        eff = delay(lambda: raiser(-1)).fmap(lambda v: v + 1).ensure(delay(increase))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 2)

        eff = delay(lambda: raiser(-1)).ensure(delay(increase)).ensure(delay(increase))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 4)

        eff = delay(lambda: raiser(-1)).ensure(delay(increase).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 6)

        eff = pure(0).ensure(delay(increase))
        await run_async(eff)
        self.assertEqual(glb, 7)

    async def test_ensure_scopes(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        def plus_one(v: int):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = delay(lambda: raiser(-1)).bind(lambda v: pure(v + 1).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 0)

        eff = pure(0).bind(lambda _: delay(lambda: raiser(-1)).ensure(delay(increase)))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 1)

        eff = (
            pure(0)
            .bind(lambda v: (
                delay(plus_one(v))
                .bind(lambda vn: pure(vn).bind(lambda _: delay(lambda: raiser(-1))))
            ))
            .ensure(delay(increase))
        )
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 2)

        eff = delay(lambda: raiser(-1)).catch_bind(TypeError, lambda _: pure(1).ensure(delay(increase)))
        self.assertEqual(await run_async(eff), 1)
        self.assertEqual(glb, 3)

    async def test_ensure_with_errors(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        async def additional_raiser(a: int):
            if a < 0:
                raise ValueError("test ensure raise")
            return None

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = delay(lambda: raiser(-1)).ensure(delay(lambda: additional_raiser(-1))).catch_fmap(ValueError, lambda _: 0)
        self.assertEqual(await run_async(eff), 0)

        eff = (
            delay(lambda: raiser(-1))
            .ensure(delay(lambda: additional_raiser(-1)))
            .ensure(delay(increase))
            .catch_fmap(ValueError, lambda _: 0)
            .fmap(lambda v: v + 1)
        )
        self.assertEqual(await run_async(eff), 1)
        self.assertEqual(glb, 1)

        eff = delay(lambda: raiser(-1)).ensure(
            delay(lambda: additional_raiser(-1)).catch_fmap(ValueError, lambda _: None)
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
        eff = pure(0).bind(lambda v: v + 1)  # type: ignore # noqa
        with self.assertRaises(MonadError):
            await run_async(eff)  # type: ignore # noqa

    async def test_run_safe(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = pure(0)
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value, 0)  # type: ignore # noqa

        eff = delay(lambda: raiser(-1)).fmap(lambda v: v + 1)
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertIsInstance(res.error, TypeError)  # type: ignore # noqa

        eff = delay(lambda: raiser(-1)).catch_fmap(TypeError, lambda _: 0).fmap(lambda v: v + 1)
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value, 1)  # type: ignore # noqa

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
            _ = retry(zero, pause_seconds_between=test)  # type: ignore # noqa
            _ = retry(zero, retry_on_result=test)  # type: ignore # noqa           

        eff = retry(
            zero,
            total_attempts=2,
            retry_on_result=lambda _: True,
            pause_seconds_between=lambda v: v - 100
        )
        with self.assertRaises(RetryBadPauseError):
            await run_async(eff)

    async def test_retry_on_exception_exhausted(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = (
            pure(0)
            .fmap(lambda v: v + 1)
            .bind(lambda _: retry(lambda: raiser(-1), total_attempts=2, retry_on_exceptions=(TypeError,)))
        )
        with self.assertRaises(RetryByExceptionError):
            await run_async(eff)

        res = await run_safe_async(eff)
        self.assertIsInstance(res, Fail)
        err = res.error  # type: ignore # noqa
        self.assertIsInstance(err, RetryByExceptionError)  # type: ignore # noqa
        self.assertIsInstance(err.exception, TypeError)  # type: ignore # noqa
        self.assertEqual(err.previous_result, 1)  # type: ignore # noqa
        self.assertEqual(err.previous_result_is_assigned, True)  # type: ignore # noqa

    async def test_retry_on_predicate_exhausted(self):
        def plus_one(v: int):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = (
            pure(0)
            .fmap(lambda v: v + 1)
            .bind(lambda v: retry(plus_one(v), total_attempts=2, retry_on_result=lambda _: True))
        )
        with self.assertRaises(RetryByValueError):
            await run_async(eff)

        res = await run_safe_async(eff)
        self.assertIsInstance(res, Fail)
        err = res.error  # type: ignore # noqa
        self.assertIsInstance(err, RetryByValueError)  # type: ignore # noqa
        self.assertEqual(err.previous_result, 1)  # type: ignore # noqa
        self.assertEqual(err.previous_result_is_assigned, True)  # type: ignore # noqa
        self.assertEqual(err.current_result, 2)  # type: ignore # noqa

    async def test_retry_on_exception_step_over(self):
        glb = 0

        def effect(value: int):
            async def effect_inner():
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
        self.assertEqual(await run_async(eff), 1)

    async def test_retry_on_predicate_step_over(self):
        def effect(value: int):
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
        eff = pure_t(0).fmap(lambda x: x + 1).fmap(lambda x: x + 1)
        self.assertEqual((await run_async(eff)).value, 2)  # type: ignore # noqa

        res = await run_safe_async(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Success)) # type: ignore # noqa
        self.assertEqual(res.value.value, 2)  # type: ignore # noqa

        eff = pure_t(0).fmap_result(lambda x: Success(x + 1)).fmap(lambda x: x + 1)
        self.assertEqual((await run_async(eff)).value, 2)  # type: ignore # noqa

        res = await run_safe_async(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Success)) # type: ignore # noqa
        self.assertEqual(res.value.value, 2)  # type: ignore # noqa

    async def test_transformer_bind_chains(self):
        eff = pure_t(0).fmap(lambda x: x + 1).bind(lambda x: lift_result(Success(x + 1)))
        self.assertEqual((await run_async(eff)).value, 2)  # type: ignore # noqa

        res = await run_safe_async(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Success)) # type: ignore # noqa
        self.assertEqual(res.value.value, 2)  # type: ignore # noqa

    async def test_transformer_inner_error(self):
        eff = error_t(0).fmap(lambda x: x + 1).fmap(lambda x: x + 1)
        self.assertIsInstance(await run_async(eff), Fail)
        self.assertEqual((await run_async(eff)).error, 0)  # type: ignore # noqa

        res = await run_safe_async(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Fail)) # type: ignore # noqa
        self.assertEqual(res.value.error, 0)  # type: ignore # noqa
        
        eff = (
            lift_result((lambda x: Fail(x) if x < 0 else Success(x))(0))
            .fmap_result(lambda x: Fail(x + 1) if x == 0 else Success(x))
            .fmap(lambda x: x + 1)
        )
        res = await run_async(eff)
        self.assertTrue(isinstance(res, Fail)) # type: ignore # noqa
        self.assertEqual(res.error, 1)  # type: ignore # noqa

        res = await run_safe_async(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Fail)) # type: ignore # noqa
        self.assertEqual(res.value.error, 1)  # type: ignore # noqa

    async def test_transformer_lift_effect(self):
        def plus_one(v: int):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = pure(0).fmap(lambda x: x + 1).bind(lambda x: delay(plus_one(x)))
        t_eff = lift_effect(eff)
        self.assertIsInstance(await run_async(t_eff), Success)  # type: ignore # noqa
        self.assertEqual((await run_async(t_eff)).value, 2)  # type: ignore # noqa

        res = await run_safe_async(t_eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Success)) # type: ignore # noqa
        self.assertEqual(res.value.value, 2)  # type: ignore # noqa

    async def test_transformer_nested_retry(self):
        g = 0

        async def raiser():
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return success(None)

        def square(val: int):
            async def square_inner():
                return success(val ** 2)
            return square_inner

        def inner_second_chain(val: int):
            return retry_t(raiser, total_attempts=3, retry_on_exceptions=(TypeError,)).fmap(lambda _: val + 1)

        def inner_first_chain(val: int):
            return (
                delay_t(square(val))
                .bind(inner_second_chain)
            )

        eff = pure_t(5).fmap(lambda v: v + 5).bind(inner_first_chain)
        self.assertEqual((await run_async(eff)).value, 101)  # type: ignore # noqa

    async def test_timeout(self):
        async def zero() -> int:
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
        self.assertIsInstance(res, Fail)
        self.assertIsInstance(res.error, TimeoutError)  # type: ignore # noqa

        eff = delay(zero, wait_seconds=0.1).catch_fmap(TimeoutError, lambda _: 1)
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

        async def cancelled(a: int):
            if a < 0:
                raise asyncio.CancelledError()            

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = delay(lambda: cancelled(-1)).catch_bind(Exception, lambda _: delay(increase))
        with self.assertRaises(asyncio.CancelledError):
            await run_async(eff)
        with self.assertRaises(asyncio.CancelledError):
            await run_safe_async(eff)
        self.assertEqual(glb, 0)

    async def test_cancelled_error_catch_intentionally(self):

        async def cancelled(a: int):
            if a < 0:
                raise asyncio.CancelledError()

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = delay(lambda: cancelled(-1)).catch_bind(asyncio.CancelledError, lambda _: delay(increase))  # type: ignore # noqa
        _ = await run_async(eff)
        self.assertEqual(glb, 1)
        _ = await run_safe_async(eff)
        self.assertEqual(glb, 2)

    async def test_cancelled_error_not_replaced(self):

        async def cancelled(a: int):
            if a < 0:
                raise asyncio.CancelledError()

        async def error_raiser(a: int):
            if a < 0:
                raise TypeError("Error")            

        eff = delay(lambda: cancelled(-1)).ensure(delay(lambda: error_raiser(-1)))
        with self.assertRaises(asyncio.CancelledError):
            await run_async(eff)
        with self.assertRaises(asyncio.CancelledError):
            await run_safe_async(eff)

    async def test_lift2(self):
        def two(a: int, b: int):
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
        def three(a: int, b: int, c: int):
            return [a, b, c]

        async def unit():
            return 1

        eff = lift3(three, pure(1), delay(unit), retry(unit))
        self.assertEqual(await run_async(eff), [1, 1, 1])

    async def test_lift4(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]

        async def unit():
            return 1

        eff = lift4(four, pure(0), delay(unit), retry(unit), pure(3))
        self.assertEqual(await run_async(eff), [0, 1, 1, 3])

    async def test_lift2_transformer(self):
        def two(a: int, b: int):
            return [a, b] 

        async def ok():
            return success(0)
        
        async def err():
            return fail(0)       

        eff = lift2_t(two, pure_t(0), pure_t(1))
        self.assertEqual((await run_async(eff)).value, [0, 1])  # type: ignore # noqa

        eff = lift2_t(two, error_t(0), pure_t(1))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

        eff = lift2_t(two, pure_t(0), error_t(1))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 1)  # type: ignore # noqa

        eff = lift2_t(two, delay_t(ok), lift_result(Success(1)))
        self.assertEqual((await run_async(eff)).value, [0, 1])  # type: ignore # noqa

        eff = lift2_t(two, delay_t(err), lift_result(Success(1)))
        res = await run_async(eff)
        self.assertTrue(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

    async def test_lift3_transformer(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        async def ok():
            return success(0)

        async def err():
            return fail(0)

        eff = lift3_t(three, pure_t(0), pure_t(1), pure_t(2))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2])  # type: ignore # noqa

        eff = lift3_t(three, error_t(0), pure_t(1), pure_t(2))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

        eff = lift3_t(three, pure_t(0), pure_t(1), error_t(2))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 2)  # type: ignore # noqa

        eff = lift3_t(three, delay_t(ok), lift_result(Success(1)), lift_effect(pure(2)))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2])  # type: ignore # noqa

        eff = lift3_t(three, delay_t(err), lift_result(Success(1)), lift_effect(pure(2)))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

    async def test_lift4_transformer(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]

        async def ok():
            return success(0)

        async def err():
            return fail(0)

        eff = lift4_t(four, pure_t(0), pure_t(1), pure_t(2), pure_t(3))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2, 3])  # type: ignore # noqa

        eff = lift4_t(four, error_t(0), pure_t(1), pure_t(2), pure_t(3))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

        eff = lift4_t(four, pure_t(0), pure_t(1), pure_t(2), error_t(3))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 3)  # type: ignore # noqa

        eff = lift4_t(four, delay_t(ok), lift_result(Success(1)), lift_effect(pure(2)), lift_effect(pure(3)))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2, 3])  # type: ignore # noqa

        eff = lift4_t(four, delay_t(err), lift_result(Success(1)), lift_effect(pure(2)), lift_effect(pure(3)))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa


if __name__ == '__main__':
    unittest.main()

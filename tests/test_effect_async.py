import unittest
import asyncio

from mafunca.common.exceptions import MonadError
from mafunca.common.exceptions import ValidationError, RetryBadPauseError, RetryByExceptionError, RetryByValueError
from mafunca.result.build import Success, Fail, success, fail
import mafunca.aff.build as af
import mafunca.aff.direct as af_dir
import mafunca.aff.flow as af_flow
import mafunca.aff.lift as af_lift
import mafunca.aff_trans.build as trans
import mafunca.aff_trans.direct as trans_dir
import mafunca.aff_trans.flow as trans_flow
import mafunca.aff_trans.lift as trans_lift
from mafunca.effect_runners import run_async, run_safe_async
from mafunca.flow import flow


class Crash(BaseException):
    pass


class TestEffectAsync(unittest.IsolatedAsyncioTestCase):
    async def test_init(self):
        async def zero():
            return 0

        eff = af.pure(0)
        self.assertEqual(await run_async(eff), 0)

        eff = af.delay(zero)
        self.assertEqual(await run_async(eff), 0)

    async def test_map(self):
        async def zero():
            return 0
        
        eff = af_dir.fmap(af_dir.fmap(af.pure(0), lambda v: v + 1), lambda v: v + 1)
        self.assertEqual(await run_async(eff), 2)

        eff = flow(
            af.delay(zero),
            af_flow.fmap(lambda v: v + 1),
            af_flow.fmap(lambda v: v + 1)
        )
        self.assertEqual(await run_async(eff), 2)

    async def test_bind(self):
        async def zero():
            return 0

        def plus_one(v: int):
            async def plus_one_inner():
                return v + 1
            return plus_one_inner

        eff = flow(
            af.pure(0),
            af_flow.bind(lambda v: af.pure(v + 1)),
            af_flow.fmap(lambda v: v + 1)
        )
        self.assertEqual(await run_async(eff), 2)

        eff = flow(
            af.pure(0),
            af_flow.bind(lambda v: af_dir.fmap(af.delay(plus_one(v)), lambda vn: vn + 1))
        )
        self.assertEqual(await run_async(eff), 2)

        eff = flow(
            af.delay(zero),
            af_flow.bind(lambda v: flow(af.pure(v + 1), af_flow.fmap(lambda v: v + 1)))
        )
        self.assertEqual(await run_async(eff), 2)

        eff = af.delay(zero)
        eff = af_dir.bind(eff, lambda v: flow(af.delay(plus_one(v)), af_flow.fmap(lambda vn: vn + 1)))
        self.assertEqual(await run_async(eff), 2)

        eff = flow(
            af.delay(zero),
            af_flow.bind(
                lambda v: flow(
                    af.delay(plus_one(v)),
                    af_flow.bind(lambda vn: af.pure(vn + 1))
                )
            )
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

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.catch_fmap(TypeError, lambda _: 0),
            af_flow.fmap(lambda v: v + 1)
        )
        self.assertEqual(await run_async(eff), 1)

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.fmap(lambda v: v + 1),
            af_flow.catch_fmap(TypeError, lambda _: 0)
        )
        self.assertEqual(await run_async(eff), 0)

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.catch_bind(TypeError, lambda _: af_dir.fmap(af.pure(0), lambda v: v + 1))
        )
        self.assertEqual(await run_async(eff), 1)

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.bind(lambda v: af.delay(plus_one(v))),
            af_flow.catch_bind(TypeError, lambda _: af_dir.bind(af.pure(0), lambda v: af.pure(v + 1))),
            af_flow.fmap(lambda v: v + 1)
        )
        self.assertEqual(await run_async(eff), 2)

    async def test_catch_no_effect_by_exception_type(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.catch_fmap(ValueError, lambda _: 0)
        )
        with self.assertRaises(TypeError):
            await run_async(eff)

    async def test_catch_no_effect_by_scope(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.bind(
                lambda v: flow(
                    af.pure(v + 1),
                    af_flow.catch_fmap(TypeError, lambda _: 0)
                )
            )
        )
        with self.assertRaises(TypeError):
            await run_async(eff)

    async def test_catch_no_effect_with_no_errors(self):
        eff = flow(
            af.pure(0),
            af_flow.bind(lambda v: af.pure(v + 1)),
            af_flow.catch_fmap(TypeError, lambda _: 0)
        )
        self.assertEqual(await run_async(eff), 1)

        eff = flow(
            af.pure(0),
            af_flow.fmap(lambda v: v + 1),
            af_flow.catch_bind(TypeError, lambda _: af.pure(0))
        )
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

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.catch_bind(TypeError, lambda _: af.delay(lambda: catcher_raiser(-1)))
        )
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

        eff = af_dir.ensure_soft(af_dir.fmap(af.pure(0), lambda v: v + 1), af.delay(increase))
        res = await run_async(eff)
        self.assertEqual(res, 1)
        self.assertEqual(glb, 1)

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.fmap(lambda v: v + 1),
            af_flow.ensure_soft(af.delay(increase))
        )
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 2)

        eff = af_dir.ensure_soft(af_dir.ensure_soft(af.delay(lambda: raiser(-1)), af.delay(increase)), af.delay(increase))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 4)

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.ensure_soft(af.delay(increase)),
            af_flow.ensure_soft(af.delay(increase))
        )
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 6)

        eff = af_dir.ensure_soft(af.pure(0), af.delay(increase))
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

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.bind(lambda v: af_dir.ensure_soft(af.pure(v + 1), af.delay(increase)))
        )
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 0)

        eff = flow(
            af.pure(0),
            af_flow.bind(lambda _: af_dir.ensure_soft(af.delay(lambda: raiser(-1)), af.delay(increase)))
        )
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 1)

        eff = flow(
            af.pure(0),
            af_flow.bind(
                lambda v: flow(
                    af.delay(plus_one(v)),
                    af_flow.bind(
                        lambda vn: flow(
                            af.pure(vn),
                            af_flow.bind(lambda _: af.delay(lambda: raiser(-1)))
                        )
                    )
                )
            ),
            af_flow.ensure_soft(af.delay(increase))
        )
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(glb, 2)

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.catch_bind(TypeError, lambda _: flow(af.pure(1), af_flow.ensure_soft(af.delay(increase))))
        )
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

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.ensure_soft(af.delay(lambda: additional_raiser(-1))),
            af_flow.catch_fmap(ValueError, lambda _: 0)
        )
        self.assertEqual(await run_async(eff), 0)

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.ensure_soft(af.delay(lambda: additional_raiser(-1))),
            af_flow.ensure_soft(af.delay(increase)),
            af_flow.catch_fmap(ValueError, lambda _: 0),
            af_flow.fmap(lambda v: v + 1)
        )
        self.assertEqual(await run_async(eff), 1)
        self.assertEqual(glb, 1)

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.ensure_soft(
                af_dir.catch_fmap(af.delay(lambda: additional_raiser(-1)), ValueError, lambda _: None)
            )
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

        eff = flow(af.delay(cancelled), af_flow.ensure_soft(af.delay(increase)))
        with self.assertRaises(asyncio.CancelledError):
            await run_async(eff)
        self.assertEqual(glb, 1)

    async def test_ensure_runs_on_task_cancell(self):
            async def imitation():                
                await asyncio.sleep(1)
    
            glb = 0
    
            async def increase():
                nonlocal glb
                glb += 1
    
            eff = flow(af.delay(imitation), af_flow.ensure_soft(af.delay(increase)))
            task = asyncio.create_task(run_async(eff))
            with self.assertRaises(asyncio.CancelledError):    
                await asyncio.sleep(0)
                task.cancel()
                await task                
            self.assertEqual(glb, 1)
            self.assertTrue(task.cancelled())

    async def test_base_exception(self):
        glb = 0

        async def crash():
            raise Crash("Crash")

        async def mark():
            nonlocal glb
            glb += 1

        eff = flow(af.delay(crash), af_flow.ensure_soft(af.delay(mark)))
        with self.assertRaises(Crash):
            await run_async(eff)
        self.assertEqual(glb, 0)

    async def test_base_exception_skips_catch_even_with_matching_handler(self):    
        log = []

        async def crash():
            raise Crash("Crash")

        eff = flow(
            af.delay(crash),
            af_flow.catch_fmap(Crash, lambda _: log.append("caught") or 0),  # type: ignore # noqa
        )
        with self.assertRaises(Crash):
            await run_async(eff)
        self.assertEqual(log, [])

    async def test_ensure_order_nested_scopes(self):
        log: list[str] = []

        def mark(name: str):

            async def inner():                
                log.append(name)

            return inner

        async def raiser():
            raise TypeError("fail")

        eff = flow(
            af.pure(0),
            af_flow.bind(lambda _: flow(
                af.delay(raiser),
                af_flow.ensure_soft(af.delay(mark("inner"))),
            )),
            af_flow.ensure_soft(af.delay(mark("outer"))),
        )
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(log, ["inner", "outer"])

    async def test_ensure_order_sequential_in_chain(self):
        log: list[str] = []

        def mark(name: str):
            async def inner():
                log.append(name)
            return inner

        async def raiser():
            raise TypeError("fail")

        eff = flow(
            af.delay(raiser),
            af_flow.ensure_soft(af.delay(mark("first"))),
            af_flow.ensure_soft(af.delay(mark("second"))),
        )
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(log, ["first", "second"])

    async def test_ensure_order_on_success(self):        
        log: list[str] = []

        def mark(name: str):
            async def inner():
                log.append(name)
            return inner

        eff = flow(
            af.pure(0),
            af_flow.bind(lambda v: flow(
                af.pure(v + 1),
                af_flow.ensure_soft(af.delay(mark("inner"))),
            )),
            af_flow.ensure_soft(af.delay(mark("outer"))),
        )
        self.assertEqual(await run_async(eff), 1)
        self.assertEqual(log, ["inner", "outer"])

    async def test_ensure_error_on_success_path_replaces_result(self):
        async def bad_finalizer():
            raise ValueError("finalizer failed")

        eff = flow(
            af.pure(42),
            af_flow.ensure_soft(af.delay(bad_finalizer)),
        )
        with self.assertRaises(ValueError):
            await run_async(eff)

        res = await run_safe_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertIsInstance(res.error, ValueError)  # type: ignore # noqa  

    async def test_ensure_error_keeps_original_in_context(self):
        async def raiser():
            raise TypeError("raised") 

        async def bad_finalizer():
            raise ValueError("finalizer failed")  

        eff = flow(
            af.delay(raiser),
            af_flow.ensure_soft(af.delay(bad_finalizer)),
        )
        with self.assertRaises(ValueError):
            await run_async(eff)
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Fail)
        error: ValueError = res.error # type: ignore # noqa   
        self.assertIsInstance(error.__context__, TypeError) 

    async def test_contract_violation(self):
        eff = af_dir.bind(af.pure(0), lambda v: v + 1)  # type: ignore # noqa
        with self.assertRaises(MonadError):
            await run_async(eff)  # type: ignore # noqa

    async def test_monad_error_not_caught_by_catch(self):   
        log = []

        eff = flow(
            af.pure(0),
            af_flow.bind(lambda v: v + 1),  # type: ignore # noqa
            af_flow.catch_fmap(Exception, lambda _: log.append("caught")),  # type: ignore # noqa
        )
        with self.assertRaises(MonadError):
            await run_async(eff)
        self.assertEqual(log, [])

    async def test_monad_error_not_swallowed_by_run_safe(self):
        eff = af_dir.bind(af.pure(0), lambda v: v + 1)  # type: ignore # noqa
        with self.assertRaises(MonadError):
            await run_safe_async(eff)  # type: ignore # noqa

    async def test_monad_error_skips_ensure(self):        
        glb = 0

        async def mark():
            nonlocal glb
            glb += 1     

        eff = flow(                         # type: ignore # noqa                     
            af.pure(0),
            af_flow.bind(lambda v: v + 1),  # type: ignore # noqa
            af_flow.ensure_soft(af.delay(mark)), # type: ignore # noqa
        )
        with self.assertRaises(MonadError):
            await run_async(eff)  # type: ignore # noqa
        self.assertEqual(glb, 0)

    async def test_run_safe(self):
        async def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = af.pure(0)
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value, 0)  # type: ignore # noqa

        eff = af_dir.fmap(af.delay(lambda: raiser(-1)), lambda v: v + 1)
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertIsInstance(res.error, TypeError)  # type: ignore # noqa

        eff = flow(
            af.delay(lambda: raiser(-1)),
            af_flow.catch_fmap(TypeError, lambda _: 0),
            af_flow.fmap(lambda v: v + 1)
        )
        res = await run_safe_async(eff)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value, 1)  # type: ignore # noqa

    async def test_retry_default_init(self):
        async def zero():
            return 0

        eff = af.retry(zero)
        self.assertEqual(await run_async(eff), 0)

    async def test_retry_bad_parameters(self):
        async def zero():
            return 0

        async def test(a: int):
            return a

        with self.assertRaises(ValidationError):
            _ = af.retry(zero, total_attempts=-2)
        with self.assertRaises(ValidationError):
            _ = af.retry(zero, pause_seconds_between=test)  # type: ignore # noqa
        with self.assertRaises(ValidationError):
            _ = af.retry(zero, retry_on_result=test)  # type: ignore # noqa           

        eff = af.retry(
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

        eff = flow(
            af.pure(0),
            af_flow.fmap(lambda v: v + 1),
            af_flow.bind(lambda _: af.retry(lambda: raiser(-1), total_attempts=2, retry_on_exceptions=(TypeError,)))
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

        eff = flow(
            af.pure(0),
            af_flow.fmap(lambda v: v + 1),
            af_flow.bind(lambda v: af.retry(plus_one(v), total_attempts=2, retry_on_result=lambda _: True))
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

        eff = flow(
            af.pure(0),
            af_flow.fmap(lambda v: v + 1),
            af_flow.bind(lambda v: af.retry(effect(v), total_attempts=3, retry_on_exceptions=(TypeError,)))
        )
        self.assertEqual(await run_async(eff), 1)

    async def test_retry_on_predicate_step_over(self):
        def effect(value: int):
            async def effect_inner():
                nonlocal value
                value += 1
                return value
            return effect_inner

        eff = flow(
            af.pure(0),
            af_flow.bind(lambda v: af.retry(effect(v), total_attempts=3, retry_on_result=lambda n: n < 3))
        )
        self.assertEqual(await run_async(eff), 3)

    async def test_retry_error_caught_by_catch_with_context_extraction(self):
        async def raiser():
            raise TypeError("always fails")

        def recover(err: RetryByExceptionError):            
            assert err.previous_result_is_assigned
            return af.pure(err.previous_result * 100)

        eff = flow(
            af.pure(0),
            af_flow.fmap(lambda v: v + 7),
            af_flow.bind(lambda _: af.retry(
                raiser, total_attempts=2, retry_on_exceptions=(TypeError,)
            )),
            af_flow.catch_bind(RetryByExceptionError, recover),
        )
        self.assertEqual(await run_async(eff), 700)

    async def test_retry_value_error_caught_and_current_result_extracted(self):
        def plus_one(v: int):
            async def inner():
                return v + 1
            return inner

        def recover(err: RetryByValueError):
            return af.pure(err.current_result)

        eff = flow(
            af.pure(0),
            af_flow.bind(lambda v: af.retry(
                plus_one(v), total_attempts=2, retry_on_result=lambda _: True
            )),
            af_flow.catch_bind(RetryByValueError, recover),
        )
        self.assertEqual(await run_async(eff), 1)

    async def test_retry_non_matching_exception_propagates_immediately(self):
        attempts = 0

        async def raiser():
            nonlocal attempts
            attempts += 1
            raise TypeError("not retryable")

        eff = af.retry(raiser, total_attempts=5, retry_on_exceptions=(ValueError,))
        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(attempts, 1)

    async def test_transformer_pure_chains(self):
        eff = flow(
            trans.pure_success(0),
            trans_flow.fmap(lambda x: x + 1),
            trans_flow.fmap(lambda x: x + 1)
        )
        self.assertEqual((await run_async(eff)).value, 2)  # type: ignore # noqa

        res = await run_safe_async(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Success)) # type: ignore # noqa
        self.assertEqual(res.value.value, 2)  # type: ignore # noqa

        eff = flow(
            trans.pure_success(0),
            trans_flow.fmap_result(lambda x: Success(x + 1)),
            trans_flow.fmap(lambda x: x + 1)
        )
        self.assertEqual((await run_async(eff)).value, 2)  # type: ignore # noqa

        res = await run_safe_async(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Success)) # type: ignore # noqa
        self.assertEqual(res.value.value, 2)  # type: ignore # noqa

    async def test_transformer_bind_chains(self):
        eff = flow(
            trans.pure_success(0),
            trans_flow.fmap(lambda x: x + 1),
            trans_flow.bind(lambda x: trans.pure_result(Success(x + 1)))
        )
        self.assertEqual((await run_async(eff)).value, 2)  # type: ignore # noqa

        res = await run_safe_async(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Success)) # type: ignore # noqa
        self.assertEqual(res.value.value, 2)  # type: ignore # noqa

    async def test_transformer_inner_error(self):
        eff = trans_dir.fmap(trans_dir.fmap(trans.pure_fail(0), lambda x: x + 1), lambda x: x + 1)
        self.assertIsInstance(await run_async(eff), Fail)
        self.assertEqual((await run_async(eff)).error, 0)  # type: ignore # noqa

        res = await run_safe_async(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertTrue(isinstance(res.value, Fail)) # type: ignore # noqa
        self.assertEqual(res.value.error, 0)  # type: ignore # noqa
        
        eff = flow(
            trans.pure_result((lambda x: Fail(x) if x < 0 else Success(x))(0)),
            trans_flow.fmap_result(lambda x: Fail(x + 1) if x == 0 else Success(x)),
            trans_flow.fmap(lambda x: x + 1)
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

        eff = flow(
            af.pure(0),
            af_flow.fmap(lambda x: x + 1),
            af_flow.bind(lambda x: af.delay(plus_one(x)))
        )
        t_eff = trans.lift_effect(eff)
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
            return trans_dir.fmap(trans.retry(raiser, total_attempts=3, retry_on_exceptions=(TypeError,)), lambda _: val + 1)

        def inner_first_chain(val: int):
            return flow(
                trans.delay(square(val)),
                trans_flow.bind(inner_second_chain)
            )

        eff = flow(
            trans.pure_success(5),
            trans_flow.fmap(lambda v: v + 5),
            trans_flow.bind(inner_first_chain)
        )
        self.assertEqual((await run_async(eff)).value, 101)  # type: ignore # noqa

    async def test_timeout(self):
        async def zero() -> int:
            await asyncio.sleep(0.2)
            return 0

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = af.delay(zero, wait_seconds=0.1)
        with self.assertRaises(TimeoutError):
            await run_async(eff)

        res = await run_safe_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertIsInstance(res.error, TimeoutError)  # type: ignore # noqa

        eff = af_dir.catch_fmap(af.delay(zero, wait_seconds=0.1), TimeoutError, lambda _: 1)
        res = await run_async(eff)
        self.assertEqual(res, 1)

        eff = af_dir.ensure_soft(af.delay(zero, wait_seconds=0.1), af.delay(increase))
        with self.assertRaises(TimeoutError):
            await run_async(eff)
        self.assertEqual(glb, 1)

    async def test_stack_safety(self):
        eff = af.pure(0)
        for _ in range(10_000):
            eff = af_dir.bind(eff, lambda v: af.pure(v + 1))
        self.assertEqual(await run_async(eff), 10_000)

    async def test_cancelled_error_not_catch(self):

        async def cancelled(a: int):
            if a < 0:
                raise asyncio.CancelledError()            

        glb = 0

        async def increase():
            nonlocal glb
            glb += 1

        eff = flow(
            af.delay(lambda: cancelled(-1)),
            af_flow.catch_bind(Exception, lambda _: af.delay(increase))
        )
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

        eff = flow(
            af.delay(lambda: cancelled(-1)),
            af_flow.catch_bind(asyncio.CancelledError, lambda _: af.delay(increase))  # type: ignore # noqa
        )
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

        eff = flow(
            af.delay(lambda: cancelled(-1)),
            af_flow.ensure_soft(af.delay(lambda: error_raiser(-1)))
        )
        with self.assertRaises(asyncio.CancelledError):
            await run_async(eff)
        with self.assertRaises(asyncio.CancelledError):
            await run_safe_async(eff)

    async def test_lift2(self):
        def two(a: int, b: int):
            return [a, b]

        async def unit():
            return 1

        eff = af_lift.lift2(two, af.pure(0), af.pure(1))
        self.assertEqual(await run_async(eff), [0, 1])

        eff = af_lift.lift2(two, af.pure(0), af.delay(unit))
        self.assertEqual(await run_async(eff), [0, 1])

        eff = af_lift.lift2(two, af.pure(0), af.retry(unit))
        self.assertEqual(await run_async(eff), [0, 1])

        eff = af_lift.lift2(two, af.delay(unit), af.retry(unit))
        self.assertEqual(await run_async(eff), [1, 1])

    async def test_lift3(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        async def unit():
            return 1

        eff = af_lift.lift3(three, af.pure(1), af.delay(unit), af.retry(unit))
        self.assertEqual(await run_async(eff), [1, 1, 1])

    async def test_lift4(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]

        async def unit():
            return 1

        eff = af_lift.lift4(four, af.pure(0), af.delay(unit), af.retry(unit), af.pure(3))
        self.assertEqual(await run_async(eff), [0, 1, 1, 3])

    async def test_lift2_transformer(self):
        def two(a: int, b: int):
            return [a, b] 

        async def ok():
            return success(0)
        
        async def err():
            return fail(0)       

        eff = trans_lift.lift2(two, trans.pure_success(0), trans.pure_success(1))
        self.assertEqual((await run_async(eff)).value, [0, 1])  # type: ignore # noqa

        eff = trans_lift.lift2(two, trans.pure_fail(0), trans.pure_success(1))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

        eff = trans_lift.lift2(two, trans.pure_success(0), trans.pure_fail(1))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 1)  # type: ignore # noqa

        eff = trans_lift.lift2(two, trans.delay(ok), trans.pure_result(Success(1)))
        self.assertEqual((await run_async(eff)).value, [0, 1])  # type: ignore # noqa

        eff = trans_lift.lift2(two, trans.delay(err), trans.pure_result(Success(1)))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

    async def test_lift3_transformer(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        async def ok():
            return success(0)

        async def err():
            return fail(0)

        eff = trans_lift.lift3(three, trans.pure_success(0), trans.pure_success(1), trans.pure_success(2))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2])  # type: ignore # noqa

        eff = trans_lift.lift3(three, trans.pure_fail(0), trans.pure_success(1), trans.pure_success(2))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

        eff = trans_lift.lift3(three, trans.pure_success(0), trans.pure_success(1), trans.pure_fail(2))
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 2)  # type: ignore # noqa

        eff = trans_lift.lift3(three, trans.delay(ok), trans.pure_result(Success(1)), trans.lift_effect(af.pure(2)))
        self.assertEqual((await run_async(eff)).value, [0, 1, 2])  # type: ignore # noqa

        eff = trans_lift.lift3(three, trans.delay(err), trans.pure_result(Success(1)), trans.lift_effect(af.pure(2)))
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

        eff = trans_lift.lift4(
            four, 
            trans.pure_success(0), 
            trans.pure_success(1), 
            trans.pure_success(2), 
            trans.pure_success(3)
        )
        self.assertEqual((await run_async(eff)).value, [0, 1, 2, 3])  # type: ignore # noqa

        eff = trans_lift.lift4(
            four, 
            trans.pure_fail(0), 
            trans.pure_success(1), 
            trans.pure_success(2), 
            trans.pure_success(3)
        )
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

        eff = trans_lift.lift4(
            four, 
            trans.pure_success(0),
            trans.pure_success(1), 
            trans.pure_success(2), 
            trans.pure_fail(3)
        )
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 3)  # type: ignore # noqa

        eff = trans_lift.lift4(
            four, 
            trans.delay(ok), 
            trans.pure_result(Success(1)), 
            trans.lift_effect(af.pure(2)), 
            trans.lift_effect(af.pure(3))
        )
        self.assertEqual((await run_async(eff)).value, [0, 1, 2, 3])  # type: ignore # noqa

        eff = trans_lift.lift4(
            four, 
            trans.delay(err), 
            trans.pure_result(Success(1)), 
            trans.lift_effect(af.pure(2)), 
            trans.lift_effect(af.pure(3))
        )
        res = await run_async(eff)
        self.assertIsInstance(res, Fail)
        self.assertEqual(res.error, 0)  # type: ignore # noqa

    async def test_cancellation_during_retry_pause(self):
        log: list[str] = []
        attempts = 0

        async def mark():
            log.append("ensure")

        async def raiser():
            nonlocal attempts
            attempts += 1
            raise TypeError("retryable")

        eff = flow(
            af.retry(
                raiser,
                total_attempts=10,
                retry_on_exceptions=(TypeError,),
                pause_seconds_between=lambda _: 5,
            ),
            af_flow.ensure_soft(af.delay(mark)),
        )

        task = asyncio.create_task(run_async(eff))
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(task.cancelled()) 
        self.assertEqual(attempts, 1) 
        self.assertEqual(log, ["ensure"])  

    async def test_stack_safety_ensure_unwind(self):        
        counter = 0

        async def inc():
            nonlocal counter
            counter += 1

        async def raiser():
            raise TypeError("bottom")

        eff = af.delay(raiser)
        for _ in range(10_000):
            eff = af_dir.ensure_soft(eff, af.delay(inc))

        with self.assertRaises(TypeError):
            await run_async(eff)
        self.assertEqual(counter, 10_000) 

    async def test_stack_safety_ensure_unwind_on_success(self):        
        counter = 0

        async def inc():
            nonlocal counter
            counter += 1

        eff = af.pure(1)
        for _ in range(10_000):
            eff = af_dir.ensure_soft(eff, af.delay(inc))

        self.assertEqual(await run_async(eff), 1)
        self.assertEqual(counter, 10_000) 

    async def test_stack_safety_catch_chain(self):        
        eff = af.pure(0)
        for _ in range(10_000):
            eff = af_dir.catch_fmap(eff, ValueError, lambda _: -1)
        self.assertEqual(await run_async(eff), 0)

    async def test_stack_safety_catch_chain_with_error_at_bottom(self):        
        async def raiser():
            raise ValueError("bottom")            

        caught = 0

        def catcher(_: Exception):
            nonlocal caught
            caught += 1
            return 7

        eff = af.delay(raiser)
        for _ in range(10_000):
            eff = af_dir.catch_fmap(eff, ValueError, catcher)

        self.assertEqual(await run_async(eff), 7)
        self.assertEqual(caught, 1)

    async def test_lift2_execution_order(self):
        log: list[str] = []

        def mk(name: str, value: int):
            async def inner():
                log.append(name)
                return value
            return inner

        eff = af_lift.lift2(
            lambda a, b: [a, b],
            af.delay(mk("a", 1)),
            af.delay(mk("b", 2)),
        )
        self.assertEqual(await run_async(eff), [1, 2])
        self.assertEqual(log, ["a", "b"])

    async def test_lift_short_circuit_skips_remaining_effects(self):       
        log: list[str] = []

        def mk_ok(name: str, value: int):
            async def inner():
                log.append(name)
                return success(value)
            return inner

        def mk_err(name: str):
            async def inner():
                log.append(name)
                return fail(0)
            return inner

        eff = trans_lift.lift3(         # type: ignore # noqa
            lambda a, b, c: [a, b, c],  # type: ignore # noqa
            trans.delay(mk_ok("a", 1)),
            trans.delay(mk_err("b")),
            trans.delay(mk_ok("c", 3)),
        )
        res = await run_async(eff)        # type: ignore # noqa
        self.assertIsInstance(res, Fail)  # type: ignore # noqa
        self.assertEqual(log, ["a", "b"])


if __name__ == '__main__':
    unittest.main()

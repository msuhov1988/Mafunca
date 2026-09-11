import unittest

from mafunca.common.exceptions import MonadError
from mafunca.common.exceptions import ValidationError, RetryBadPauseError, RetryByExceptionError, RetryByValueError
from mafunca.result.build import success, fail, Success, Fail
import mafunca.eff.build as ef
import mafunca.eff.direct as ef_dir
import mafunca.eff.flow as ef_flow
import mafunca.eff.lift as ef_lift
import mafunca.eff_trans.build as trans
import mafunca.eff_trans.direct as trans_dir
import mafunca.eff_trans.flow as trans_flow
import mafunca.eff_trans.lift as trans_lift
from mafunca.effect_runners import run, run_safe
from mafunca.flow import flow


class Crash(BaseException):
    pass


class TestEffectSync(unittest.TestCase):
    def test_init(self):
        eff = ef.pure(0)
        self.assertEqual(run(eff), 0)

        eff = ef.delay(lambda: 0)
        self.assertEqual(run(eff), 0)

    def test_map(self):
        eff = flow(ef.pure(0), ef_flow.fmap(lambda v: v + 1), ef_flow.fmap(lambda v: v + 1))
        self.assertEqual(run(eff), 2)

        eff = ef.delay(lambda: 0)
        eff = ef_dir.fmap(eff, lambda v: v + 1)
        eff = ef_dir.fmap(eff, lambda v: v + 1)
        self.assertEqual(run(eff), 2)

    def test_bind(self):
        eff = flow(
            ef.pure(0), 
            ef_flow.bind(
                lambda v: flow(
                    ef.pure(v + 1),
                    ef_flow.fmap(lambda v: v + 1)
                )
            )
        )
        self.assertEqual(run(eff), 2)

        eff = ef.pure(0)
        eff = ef_dir.bind(eff, lambda v: flow(ef.delay(lambda: v + 1), ef_flow.fmap(lambda vn: vn + 1)))
        self.assertEqual(run(eff), 2)

        eff = flow(
            ef.delay(lambda: 0),
            ef_flow.bind(
                lambda v: flow(
                    ef.pure(v + 1), 
                    ef_flow.fmap(lambda v: v + 1)
                )
            )
        )
        self.assertEqual(run(eff), 2)

        eff = ef.delay(lambda: 0)
        eff = ef_dir.bind(eff, lambda v: flow(ef.delay(lambda: v + 1), ef_flow.fmap(lambda vn: vn + 1)))
        self.assertEqual(run(eff), 2)

        eff = flow(
            ef.delay(lambda: 0),
            ef_flow.bind(
                lambda v: flow(
                    ef.delay(lambda: v + 1),
                    ef_flow.bind(lambda vn: ef.pure(vn + 1))
                )
            )
        )
        self.assertEqual(run(eff), 2)

    def test_catch(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.catch_fmap(TypeError, lambda _: 0),
            ef_flow.fmap(lambda v: v + 1)
        )
        self.assertEqual(run(eff), 1)

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.fmap(lambda v: v + 1),
            ef_flow.catch_fmap(TypeError, lambda _: 0)
        )
        self.assertEqual(run(eff), 0)

        eff = flow(
            ef.delay(lambda: raiser(10)),
            ef_flow.catch_bind(TypeError, lambda _: ef.pure(0)),
            ef_flow.fmap(lambda v: v + 1)
        )
        self.assertEqual(run(eff), 11)

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.bind(lambda v: ef.delay(lambda: v + 100)),
            ef_flow.catch_bind(TypeError, lambda _: ef_dir.bind(ef.pure(0), lambda v: ef.pure(v + 1))),
            ef_flow.fmap(lambda v: v + 1)
        )
        self.assertEqual(run(eff), 2)

    def test_catch_no_effect_by_exception_type(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.catch_fmap(ValueError, lambda _: 0)
        )
        with self.assertRaises(TypeError):
            run(eff)

    def test_catch_no_effect_by_scope(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.bind(lambda v: flow(ef.pure(v + 1), ef_flow.catch_fmap(TypeError, lambda _: 0)))
        )
        with self.assertRaises(TypeError):
            run(eff)

    def test_catch_no_effect_with_no_errors(self):
        eff = flow(
            ef.pure(0),
            ef_flow.bind(
                lambda v: flow(
                    ef.pure(v + 1),
                    ef_flow.catch_fmap(TypeError, lambda _: 0)
                )
            )
        )
        self.assertEqual(run(eff), 1)

        eff = ef.pure(0)
        eff = ef_dir.fmap(eff, lambda v: v + 1)
        eff = ef_dir.catch_bind(eff, TypeError, lambda _: ef.pure(0))
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


        eff = ef.delay(lambda: raiser(-10))
        eff = ef_dir.catch_bind(eff, TypeError, lambda _: ef.delay(lambda: catcher_raiser(-10)))
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

        eff = flow(
            ef.delay(lambda: 0),
            ef_flow.fmap(lambda v: v + 1),
            ef_flow.ensure(ef.delay(increase))
        )
        res = run(eff)
        self.assertEqual(res, 1)
        self.assertEqual(glb, 1)

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.fmap(lambda v: v + 1),
            ef_flow.ensure(ef.delay(increase))
        )
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 2)

        eff = ef.delay(lambda: raiser(-10))
        eff = ef_dir.ensure(eff, ef.delay(increase))
        eff = ef_dir.ensure(eff, ef.delay(increase))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 4)

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.ensure(ef.delay(increase)),
            ef_flow.ensure(ef.delay(increase)),
        )
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 6)

        eff = ef_dir.ensure(ef.pure(0), ef.delay(increase))
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

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.bind(lambda v: ef_dir.ensure(ef.pure(v + 1), ef.delay(increase)))
        )
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 0)

        eff = flow(
            ef.pure(0),
            ef_flow.bind(lambda _: ef_dir.ensure(ef.delay(lambda: raiser(-10)), ef.delay(increase)))
        )
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 1)

        eff = flow(
            ef.pure(0),
            ef_flow.bind(
                lambda v: flow(
                    ef.delay(lambda: v + 1),
                    ef_flow.bind(
                        lambda vn: flow(
                            ef.pure(vn),
                            ef_flow.bind(lambda _: ef.delay(lambda: raiser(-10)))
                        )
                    )
                )
            ),
            ef_flow.ensure(ef.delay(increase)),
        )
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(glb, 2)

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.catch_bind(TypeError, lambda _: ef_dir.ensure(ef.pure(1), ef.delay(increase)))
        )
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

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.ensure(ef.delay(lambda: additional_raiser(-10))),
            ef_flow.catch_fmap(ValueError, lambda _: 0)
        )
        self.assertEqual(run(eff), 0)

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.ensure(ef.delay(lambda: additional_raiser(-10))),
            ef_flow.ensure(ef.delay(increase)),
            ef_flow.catch_fmap(ValueError, lambda _: 0),
            ef_flow.fmap(lambda v: v + 1),
        )        
        self.assertEqual(run(eff), 1)
        self.assertEqual(glb, 1)

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.ensure(
                flow(
                    ef.delay(lambda: additional_raiser(-10)),
                    ef_flow.catch_fmap(ValueError, lambda _: None)
                )
            )
        )        
        with self.assertRaises(TypeError):
            run(eff)

    def test_base_exception(self):
        glb = 0

        def crash():
            raise Crash("Crash")

        def mark():
            nonlocal glb
            glb += 1

        eff = flow(ef.delay(crash), ef_flow.ensure(ef.delay(mark)))
        with self.assertRaises(Crash):
            run(eff)
        self.assertEqual(glb, 0)

    def test_base_exception_skips_catch_even_with_matching_handler(self):    
        log = []

        def crash():
            raise Crash("Crash")

        eff = flow(
            ef.delay(crash),
            ef_flow.catch_fmap(Crash, lambda _: log.append("caught") or 0),  # type: ignore # noqa
        )
        with self.assertRaises(Crash):
            run(eff)
        self.assertEqual(log, [])

    def test_ensure_order_nested_scopes(self):
        log: list[str] = []

        def mark(name: str):

            def inner():                
                log.append(name)

            return inner

        def raiser():
            raise TypeError("fail")

        eff = flow(
            ef.pure(0),
            ef_flow.bind(lambda _: flow(
                ef.delay(raiser),
                ef_flow.ensure(ef.delay(mark("inner"))),
            )),
            ef_flow.ensure(ef.delay(mark("outer"))),
        )
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(log, ["inner", "outer"])

    def test_ensure_order_sequential_in_chain(self):
        log: list[str] = []

        def mark(name: str):
            def inner():
                log.append(name)
            return inner

        def raiser():
            raise TypeError("fail")

        eff = flow(
            ef.delay(raiser),
            ef_flow.ensure(ef.delay(mark("first"))),
            ef_flow.ensure(ef.delay(mark("second"))),
        )
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(log, ["first", "second"])

    def test_ensure_order_on_success(self):        
        log: list[str] = []

        def mark(name: str):
            def inner():
                log.append(name)
            return inner

        eff = flow(
            ef.pure(0),
            ef_flow.bind(lambda v: flow(
                ef.pure(v + 1),
                ef_flow.ensure(ef.delay(mark("inner"))),
            )),
            ef_flow.ensure(ef.delay(mark("outer"))),
        )
        self.assertEqual(run(eff), 1)
        self.assertEqual(log, ["inner", "outer"])

    def test_ensure_error_on_success_path_replaces_result(self):
        def bad_finalizer():
            raise ValueError("finalizer failed")

        eff = flow(
            ef.pure(42),
            ef_flow.ensure(ef.delay(bad_finalizer)),
        )
        with self.assertRaises(ValueError):
            run(eff)

        res = run_safe(eff)
        self.assertIsInstance(res, Fail)
        self.assertIsInstance(res.error, ValueError)  # type: ignore # noqa  

    def test_ensure_error_keeps_original_in_context(self):
        def raiser():
            raise TypeError("raised") 

        def bad_finalizer():
            raise ValueError("finalizer failed")  

        eff = flow(
            ef.delay(raiser),
            ef_flow.ensure(ef.delay(bad_finalizer)),
        )
        with self.assertRaises(ValueError):
            run(eff)
        res = run_safe(eff)
        self.assertIsInstance(res, Fail)
        error: ValueError = res.error # type: ignore # noqa   
        self.assertIsInstance(error.__context__, TypeError) 

    def test_contract_violation(self):
        eff = flow(ef.delay(lambda: 0), ef_flow.bind(lambda v: v + 1))  # type: ignore # noqa
        with self.assertRaises(MonadError):
            run(eff)  # type: ignore # noqa

    def test_retry_error_caught_by_catch_with_context_extraction(self):
        def raiser():
            raise TypeError("always fails")

        def recover(err: RetryByExceptionError):            
            assert err.previous_result_is_assigned
            return ef.pure(err.previous_result * 100)

        eff = flow(
            ef.pure(0),
            ef_flow.fmap(lambda v: v + 7),
            ef_flow.bind(lambda _: ef.retry(
                raiser, total_attempts=2, retry_on_exceptions=(TypeError,)
            )),
            ef_flow.catch_bind(RetryByExceptionError, recover),
        )
        self.assertEqual(run(eff), 700)

    def test_retry_value_error_caught_and_current_result_extracted(self):
        def plus_one(v: int):
            def inner():
                return v + 1
            return inner

        def recover(err: RetryByValueError):
            return ef.pure(err.current_result)

        eff = flow(
            ef.pure(0),
            ef_flow.bind(lambda v: ef.retry(
                plus_one(v), total_attempts=2, retry_on_result=lambda _: True
            )),
            ef_flow.catch_bind(RetryByValueError, recover),
        )
        self.assertEqual(run(eff), 1)

    def test_retry_non_matching_exception_propagates_immediately(self):
        attempts = 0

        def raiser():
            nonlocal attempts
            attempts += 1
            raise TypeError("not retryable")

        eff = ef.retry(raiser, total_attempts=5, retry_on_exceptions=(ValueError,))
        with self.assertRaises(TypeError):
            run(eff)
        self.assertEqual(attempts, 1)

    def test_run_safe(self):
        def raiser(a: int):
            if a < 0:
                raise TypeError("test raise")
            return a

        eff = ef.pure(0)
        res = run_safe(eff)
        self.assertIsInstance(res, Success)
        res = res.value if isinstance(res, Success) else -1
        self.assertEqual(res, 0)

        eff = ef_dir.fmap(ef.delay(lambda: raiser(-10)), lambda v: v + 1)
        res = run_safe(eff)
        self.assertIsInstance(res, Fail)
        res = res.error if isinstance(res, Fail) else -1
        self.assertIsInstance(res, TypeError)

        eff = flow(
            ef.delay(lambda: raiser(-10)),
            ef_flow.catch_fmap(TypeError, lambda _: 0),
            ef_flow.fmap(lambda v: v + 1)
        )
        res = run_safe(eff)
        self.assertIsInstance(res, Success)
        res = res.value if isinstance(res, Success) else -1
        self.assertEqual(res, 1)

    def test_retry_default_init(self):
        eff = ef.retry(lambda: 0)
        self.assertEqual(run(eff), 0)

    def test_retry_bad_parameters(self):
        async def test(a: int):
            return a

        with self.assertRaises(ValidationError):
            _ = ef.retry(lambda: 0, total_attempts=-2)
        with self.assertRaises(ValidationError):
            _ = ef.retry(lambda: 0, pause_seconds_between=test)  # type: ignore # noqa
        with self.assertRaises(ValidationError):
            _ = ef.retry(lambda: 0, retry_on_result=test)  # type: ignore # noqa            

        eff = ef.retry(
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

        eff = flow(
            ef.pure(0),
            ef_flow.fmap(lambda v: v + 1),
            ef_flow.bind(lambda _: ef.retry(lambda: raiser(-1), total_attempts=2, retry_on_exceptions=(TypeError,)))
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
        eff = flow(
            ef.pure(0),
            ef_flow.fmap(lambda v: v + 1),
            ef_flow.bind(lambda v: ef.retry(lambda: v + 1, total_attempts=2, retry_on_result=lambda _: True))
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

        eff = flow(
            ef.pure(0),
            ef_flow.fmap(lambda v: v + 1),
            ef_flow.bind(lambda v: ef.retry(effect(v), total_attempts=3, retry_on_exceptions=(TypeError,)))
        )
        self.assertEqual(run(eff), 1)

    def test_retry_on_predicate_step_over(self):
        def effect(value: int):
            def effect_inner():
                nonlocal value
                value += 1
                return value
            return effect_inner

        eff = flow(
            ef.pure(0),
            ef_flow.bind(lambda v: ef.retry(effect(v), total_attempts=3, retry_on_result=lambda n: n < 3))
        )
        self.assertEqual(run(eff), 3)

    def test_transformer_pure_chains(self):
        eff = flow(
            trans.pure_success(0),
            trans_flow.fmap(lambda x: x + 1),
            trans_flow.fmap(lambda x: x + 1)
        )
        res = run(eff)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value if isinstance(res, Success) else 0, 2)

        res = run_safe(eff)
        self.assertTrue(isinstance(res, Success))
        res_inner = res.value if isinstance(res, Success) else 0
        self.assertTrue(isinstance(res_inner, Success))
        value = res_inner.value if isinstance(res_inner, Success) else 0
        self.assertEqual(value, 2)

        eff = flow(
            trans.pure_success(0),
            trans_flow.fmap_result(lambda x: Success(x + 1)),
            trans_flow.fmap(lambda x: x + 1)
        )
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
        eff = flow(
            trans.pure_success(0),
            trans_flow.fmap(lambda x: x + 1),
            trans_flow.bind(lambda x: trans.pure_result(Success(x + 1)))
        )
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
        eff = trans.pure_fail(0)
        eff = trans_dir.fmap(eff, lambda x: x + 1)
        eff = trans_dir.fmap(eff, lambda x: x + 1)
        res = run(eff)
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

        res = run_safe(eff)
        self.assertTrue(isinstance(res, Success))
        res_inner = res.value if isinstance(res, Success) else 100
        self.assertTrue(isinstance(res_inner, Fail))
        value = res_inner.error if isinstance(res_inner, Fail) else 100
        self.assertEqual(value, 0)

        eff = flow(
            trans.pure_result((lambda x: Fail(x) if x < 0 else Success(x))(0)),
            trans_flow.fmap_result(lambda x: Fail(x + 1) if x == 0 else Success(x)),
            trans_flow.fmap(lambda x: x + 1)
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
        eff = flow(
            ef.pure(0),
            ef_flow.fmap(lambda x: x + 1),
            ef_flow.bind(lambda x: ef.delay(lambda: x + 1))
        )
        t_eff = trans.lift_effect(eff)
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
            return trans_dir.fmap(trans.retry(raiser, total_attempts=3, retry_on_exceptions=(TypeError,)), lambda _: val + 1)

        def inner_first_chain(val: int):
            return flow(
                trans.delay(lambda: success(val ** 2)),
                trans_flow.bind(inner_second_chain)
            )

        eff = flow(
            trans.pure_success(5),
            trans_flow.fmap(lambda v: v + 5),
            trans_flow.bind(inner_first_chain)
        )
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, 101)

    def test_stack_safety(self):
        eff = ef.pure(0)
        for _ in range(10_000):
            eff = ef_dir.bind(eff, lambda v: ef.pure(v + 1))
        self.assertEqual(run(eff), 10_000)

    def test_lift2(self):
        def two(a: int, b: int):
            return [a, b]

        eff = ef_lift.lift2(two, ef.pure(0), ef.pure(1))
        self.assertEqual(run(eff), [0, 1])

        eff = ef_lift.lift2(two, ef.pure(0), ef.delay(lambda: 1))
        self.assertEqual(run(eff), [0, 1])

        eff = ef_lift.lift2(two, ef.pure(0), ef.retry(lambda: 1))
        self.assertEqual(run(eff), [0, 1])

        eff = ef_lift.lift2(two, ef.delay(lambda: 0), ef.retry(lambda: 1))
        self.assertEqual(run(eff), [0, 1])

    def test_lift3(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        eff = ef_lift.lift3(three, ef.pure(0), ef.delay(lambda: 1), ef.retry(lambda: 2))
        self.assertEqual(run(eff), [0, 1, 2])

    def test_lift4(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]

        eff = ef_lift.lift4(four, ef.pure(0), ef.delay(lambda: 1), ef.retry(lambda: 2), ef.pure(3))
        self.assertEqual(run(eff), [0, 1, 2, 3])

    def test_lift2_transformer(self):
        def two(a: int, b: int):
            return [a, b]

        eff = trans_lift.lift2(two, trans.pure_success(0), trans.pure_success(1))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1])

        eff = trans_lift.lift2(two, trans.pure_fail(0), trans.pure_success(1))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

        eff = trans_lift.lift2(two, trans.pure_success(0), trans.pure_fail(1))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 1)

        eff = trans_lift.lift2(two, trans.delay(lambda: success(0)), trans.pure_result(success(1)))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1])

        eff = trans_lift.lift2(two, trans.delay(lambda: fail(0)), trans.pure_result(success(1)))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

    def test_lift3_transformer(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        eff = trans_lift.lift3(three, trans.pure_success(0), trans.pure_success(1), trans.pure_success(2))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1, 2])        

        eff = trans_lift.lift3(three, trans.pure_fail(0), trans.pure_success(1), trans.pure_success(2))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

        eff = trans_lift.lift3(three, trans.pure_success(0), trans.pure_success(1), trans.pure_fail(2))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 2)

        eff = trans_lift.lift3(three, trans.delay(lambda: success(0)), trans.pure_result(success(1)), trans.lift_effect(ef.pure(2)))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1, 2])

        eff = trans_lift.lift3(three, trans.delay(lambda: fail(0)), trans.pure_result(success(1)), trans.lift_effect(ef.pure(2)))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

    def test_lift4_transformer(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]

        eff = trans_lift.lift4(four, trans.pure_success(0), trans.pure_success(1), trans.pure_success(2), trans.pure_success(3))
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1, 2, 3])

        eff = trans_lift.lift4(four, trans.pure_fail(0), trans.pure_success(1), trans.pure_success(2), trans.pure_success(3))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)

        eff = trans_lift.lift4(four, trans.pure_success(0), trans.pure_success(1), trans.pure_success(2), trans.pure_fail(3))
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 3)

        eff = trans_lift.lift4(
            four, 
            trans.delay(lambda: success(0)), 
            trans.pure_result(success(1)), 
            trans.lift_effect(ef.pure(2)), 
            trans.lift_effect(ef.pure(3))
        )
        res = run(eff)
        self.assertTrue(isinstance(res, Success))
        self.assertEqual(res.value if isinstance(res, Success) else 0, [0, 1, 2, 3])

        eff = trans_lift.lift4(
            four, 
            trans.delay(lambda: fail(0)), 
            trans.pure_result(success(1)), 
            trans.lift_effect(ef.pure(2)), 
            trans.lift_effect(ef.pure(3))
        )
        res = run(eff)
        self.assertTrue(isinstance(res, Fail))
        self.assertEqual(res.error if isinstance(res, Fail) else 100, 0)


if __name__ == '__main__':
    unittest.main()

import unittest
from typing import Any

from mafunca.result.build import Success, Fail
from mafunca.aff.build import pure, delay, delay_to_thread, retry, do, step, Do
from mafunca.aff.direct import catch_bind
from mafunca.effect_runners_gen_based import run_async, run_safe_async

  
async def _async_value(value: int):
    return value


async def _async_raise(exc: BaseException):
    raise exc


class TestAffGenBased(unittest.IsolatedAsyncioTestCase):

    async def test_run_async_simple_generator_happy_path(self):
        @do
        def workflow() -> Do[int]:
            a = yield from step(pure(10))
            b = yield from step(delay(lambda: _async_value(20)))
            return a + b

        result = await run_async(workflow())
        self.assertEqual(result, 30)

    async def test_run_async_nested_generator_workflow(self):
        @do
        def inner() -> Do[int]:
            x = yield from step(delay(lambda: _async_value(3)))
            y = yield from step(pure(4))
            return x * y

        @do
        def outer()  -> Do[int]:
            a = yield from step(pure(2))
            b = yield from step(inner())
            c = yield from step(delay(lambda: _async_value(5)))
            return a + b + c

        result = await run_async(outer())
        self.assertEqual(result, 19)

    async def test_run_async_exception_thrown_into_generator_and_recovered_by_try_except(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int | None]:
            trace.append("start")
            try:
                yield from step(delay(lambda: _async_raise(ValueError("boom"))))
            except ValueError as exc:
                trace.append(f"handled:{exc}")
                recovered = yield from step(pure(100))
                return recovered + 1
            finally:
                trace.append("finally")

        result = await run_async(workflow())
        self.assertEqual(result, 101)
        self.assertEqual(trace, ["start", "handled:boom", "finally"])

    async def test_run_async_multiple_failures_before_success_inside_generator(self):
        state = {"n": 0}

        async def flaky():
            state["n"] += 1
            if state["n"] < 3:
                raise ValueError(f"fail-{state['n']}")
            return 50

        @do
        def workflow() -> Do[int]:
            total = 0
            for _ in range(3):
                try:
                    total += yield from step(delay(flaky))
                except ValueError:
                    total += 1
            return total

        result = await run_async(workflow())
        self.assertEqual(result, 52)
        self.assertEqual(state["n"], 3)

    async def test_run_async_delay_to_thread_inside_generator(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int]:
            a = yield from step(delay_to_thread(lambda: trace.append("thread-step") or 7))
            b = yield from step(pure(5))
            return a + b

        result = await run_async(workflow())
        self.assertEqual(result, 12)
        self.assertEqual(trace, ["thread-step"])

    async def test_run_async_generator_finally_executes_when_effect_raises_and_is_not_caught(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[None]:
            try:
                yield from step(delay(lambda: _async_raise(ValueError("boom"))))
            finally:
                trace.append("generator-finally")

        with self.assertRaises(ValueError):
            await run_async(workflow())

        self.assertEqual(trace, ["generator-finally"])

    async def test_run_safe_async_wraps_exception_into_fail(self):
        @do
        def workflow() -> Do[int]:
            a = yield from step(pure(1))
            b = yield from step(delay(lambda: _async_raise(ValueError("bad"))))
            return a + b

        result = await run_safe_async(workflow())
        self.assertIsInstance(result, Fail)
        self.assertIsInstance(result.error if isinstance(result, Fail) else None, ValueError)
        self.assertEqual(str(result.error if isinstance(result, Fail) else None), "bad")

    async def test_run_safe_async_does_not_wrap_baseexception(self):
        @do
        def workflow() -> Do[int]:
            yield from step(delay(lambda: _async_raise(KeyboardInterrupt())))
            return 1

        with self.assertRaises(KeyboardInterrupt):
            await run_safe_async(workflow())

    async def test_run_safe_async_success_path(self):
        @do
        def workflow() -> Do[int]:
            x = yield from step(delay(lambda: _async_value(5)))
            y = yield from step(delay(lambda: _async_value(6)))
            return x * y

        result = await run_safe_async(workflow())
        self.assertEqual(result, Success(30))

    async def test_nested_generator_exception_propagates_to_outer_generator(self):
        trace: list[str] = []

        @do
        def inner() -> Do[None]:
            trace.append("inner:start")
            yield from step(delay(lambda: _async_raise(ValueError("inner-boom"))))

        @do
        def outer() -> Do[str | None]:
            trace.append("outer:start")
            try:
                yield from step(inner())
            except ValueError as exc:
                trace.append(f"outer:caught:{exc}")
                return "recovered"

        result = await run_async(outer())
        self.assertEqual(result, "recovered")
        self.assertEqual(trace, ["outer:start", "inner:start", "outer:caught:inner-boom"])

    async def test_generator_close_happens_for_nested_workflow_finally(self):
        trace: list[str] = []

        @do
        def inner() -> Do[None]:
            try:
                yield from step(pure(1))
                yield from step(delay(lambda: _async_raise(ValueError("boom"))))
            finally:
                trace.append("inner-finally")

        @do
        def outer() -> Do[None]:
            try:
                yield from step(inner())
            finally:
                trace.append("outer-finally")

        with self.assertRaises(ValueError):
            await run_async(outer())

        self.assertEqual(trace, ["inner-finally", "outer-finally"])

    async def test_nested_generators_outer_catches_inner_error_both_finally_execute_and_outer_recovers(self):
        trace: list[str] = []

        @do
        def inner() -> Do[None]:
            trace.append("inner:start")
            try:
                yield from step(pure(1))
                yield from step(delay(lambda: _async_raise(RuntimeError("boom"))))
            finally:
                trace.append("inner:finally")

        @do
        def outer() -> Do[int | None]:
            trace.append("outer:start")
            try:
                yield from step(inner())
            except RuntimeError as exc:
                trace.append(f"outer:except:{exc}")
                fallback = yield from step(delay(lambda: _async_value(20)))
                return fallback + 1
            finally:
                trace.append("outer:finally")

        result = await run_async(outer())

        self.assertEqual(result, 21)
        self.assertEqual(
            trace,
            [
                "outer:start",
                "inner:start",
                "inner:finally",
                "outer:except:boom",
                "outer:finally",
            ]
        )

    async def test_three_level_nested_generators_exception_rethrown_transformed_and_all_finally_execute(self):
        trace: list[str] = []

        @do
        def leaf() -> Do[None]:
            trace.append("leaf:start")
            try:
                yield from step(delay(lambda: _async_raise(ValueError("leaf-error"))))
            finally:
                trace.append("leaf:finally")

        @do
        def middle() -> Do[None]:
            trace.append("middle:start")
            try:
                yield from step(leaf())
            except ValueError as exc:
                trace.append(f"middle:except:{exc}")
                raise KeyError("middle-transformed")
            finally:
                trace.append("middle:finally")

        @do
        def outer() -> Do[int | None]:
            trace.append("outer:start")
            try:
                yield from step(middle())
            except KeyError as exc:
                trace.append(f"outer:except:{exc}")
                val = yield from step(delay(lambda: _async_value(100)))
                return val + 23
            finally:
                trace.append("outer:finally")

        result = await run_async(outer())

        self.assertEqual(result, 123)
        self.assertEqual(
            trace,
            [
                "outer:start",
                "middle:start",
                "leaf:start",
                "leaf:finally",
                "middle:except:leaf-error",
                "middle:finally",
                "outer:except:'middle-transformed'",
                "outer:finally",
            ]
        )

    async def test_retry_retries_on_async_result_until_success(self):
        trace: list[str] = []
        state = {"attempt": 0}

        async def flaky():
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            if state["attempt"] < 3:
                return 0
            return 10

        @do
        def workflow() -> Do[int]:
            value = yield from step(
                retry(
                    flaky,
                    total_attempts=5,
                    retry_on_result=lambda r: r == 0,
                    step_name="flaky_async_step",
                )
            )
            trace.append(f"value:{value}")
            return value + 5

        result = await run_async(workflow())

        self.assertEqual(result, 15)
        self.assertEqual(state["attempt"], 3)
        self.assertEqual(
            trace,
            [
                "attempt:1",
                "attempt:2",
                "attempt:3",
                "value:10",
            ]
        )

    async def test_retry_retries_on_exception_and_then_recovers(self):
        trace: list[str] = []
        state = {"attempt": 0}

        async def flaky():
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            if state["attempt"] < 3:
                raise ValueError(f"boom-{state['attempt']}")
            return 8

        @do
        def workflow() -> Do[int]:
            value = yield from step(
                retry(
                    flaky,
                    total_attempts=4,
                    retry_on_exceptions=(ValueError,),
                    step_name="exception_retry_step",
                )
            )
            trace.append(f"value:{value}")
            return value * 2

        result = await run_async(workflow())

        self.assertEqual(result, 16)
        self.assertEqual(state["attempt"], 3)
        self.assertEqual(
            trace,
            [
                "attempt:1",
                "attempt:2",
                "attempt:3",
                "value:8",
            ]
        )

    async def test_retry_stops_on_first_non_retryable_exception(self):
        trace: list[str] = []
        state = {"attempt": 0}

        async def flaky():
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            raise TypeError("fatal")

        @do
        def workflow() -> Do[Any]:
            return (
                yield from step(
                    retry(
                        flaky,
                        total_attempts=5,
                        retry_on_exceptions=(ValueError,),
                        step_name="non_retryable",
                    )
                )
            )

        with self.assertRaises(TypeError) as ctx:
            await run_async(workflow())

        self.assertEqual(str(ctx.exception), "fatal")
        self.assertEqual(state["attempt"], 1)
        self.assertEqual(trace, ["attempt:1"])

    async def test_retry_result_predicate_is_not_checked_after_successful_terminal_result(self):
        trace: list[str] = []
        state = {"attempt": 0}

        async def flaky():
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            return 7 if state["attempt"] == 1 else 999

        @do
        def workflow() -> Do[int]:
            value = yield from step(
                retry(
                    flaky,
                    total_attempts=5,
                    retry_on_result=lambda r: r < 0,
                    step_name="terminal-success",
                )
            )
            trace.append(f"value:{value}")
            return value

        result = await run_async(workflow())

        self.assertEqual(result, 7)
        self.assertEqual(state["attempt"], 1)
        self.assertEqual(trace, ["attempt:1", "value:7"])

    async def test_run_async_exception_inside_effect_can_be_caught_via_catch_bind(self):
        effect = catch_bind(
            delay(lambda: _async_raise(ZeroDivisionError("boom"))),
            ZeroDivisionError,
            lambda exc: pure(f"caught: {exc.__class__.__name__}")
        )

        @do
        def workflow() -> Do[str]:
            value = yield from step(effect)
            return value

        result = await run_async(workflow())
        self.assertEqual(result, "caught: ZeroDivisionError")   

    async def test_chained_exceptions(self):
        glb: list[str | int] = []

        @do
        def chained_exceptions() -> Do[None]:
            nonlocal glb
            try:
                yield from step(delay(lambda: _async_value(int(1 / 0))))
            except ZeroDivisionError:                
                glb.append("zero-div")
                try:
                    raise ValueError("boom")  
                except ValueError:
                    glb.append("value-err")
                    norm = yield from step(delay(lambda: _async_value(0)))
                    glb.append(norm)
                    raise TypeError("err")

            finally:
                glb.append("finally")

        with self.assertRaises(TypeError):
            await run_async(chained_exceptions())        
        self.assertEqual(glb, ["zero-div", "value-err", 0, "finally"])


if __name__ == '__main__':
    unittest.main()

import unittest

from mafunca.result.build import Success, Fail, success, fail, Result
from mafunca.aff.build import pure as aff_pure, delay as aff_delay
from mafunca.aff_trans.build import (
    AffResultGenBased,
    pure_success,
    pure_fail,
    pure_result,
    lift_effect,
    delay,
    delay_to_thread,
    retry,
    step,
    do,
    Do,
)
from mafunca.effect_runners_gen_based import run_async, run_safe_async


async def _async_value(value: int):
    return value


async def _async_result(value: Result[int, str]):
    return value


async def _async_raise(exc: BaseException):
    raise exc


async def _async_trace_and_return(trace: list[str], label: str, value: int):
    trace.append(label)
    return value


async def _async_trace_and_result(trace: list[str], label: str, result: Result[int, str]):
    trace.append(label)
    return result


class TestAffResultGenBased(unittest.IsolatedAsyncioTestCase):

    async def test_run_async_returns_success_on_plain_happy_path(self):
        @do
        def workflow() -> Do[int, int]:
            a = yield from step(pure_success(10))
            b = yield from step(pure_success(20))
            return a + b

        result = await run_async(workflow())
        self.assertEqual(result, Success(30))

    async def test_final_return_is_wrapped_into_success(self):
        @do
        def workflow() -> Do[int, int]:
            yield from step(pure_success(0))
            return 123

        result = await run_async(workflow())
        self.assertEqual(result, Success(123))

    async def test_pure_fail_short_circuits_immediately(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            trace.append("before")
            yield from step(pure_fail("boom"))
            trace.append("after")
            return 999

        result = await run_async(workflow())
        self.assertEqual(result, Fail("boom"))
        self.assertEqual(trace, ["before"])

    async def test_pure_result_success_is_unwrapped(self):
        @do
        def workflow() -> Do[int, int]:
            value = yield from step(pure_result(success(7)))
            return value * 6

        result = await run_async(workflow())
        self.assertEqual(result, Success(42))

    async def test_pure_result_fail_short_circuits(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            trace.append("start")
            yield from step(pure_result(fail("err")))
            trace.append("unreachable")
            return 1

        result = await run_async(workflow())
        self.assertEqual(result, Fail("err"))
        self.assertEqual(trace, ["start"])

    async def test_delay_success_result_is_unwrapped(self):
        @do
        def workflow() -> Do[int, str]:
            a = yield from step(delay(lambda: _async_result(success(5))))
            b = yield from step(delay(lambda: _async_result(success(8))))
            return a * b

        result = await run_async(workflow())
        self.assertEqual(result, Success(40))

    async def test_delay_fail_result_short_circuits(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            trace.append("before")
            yield from step(delay(lambda: _async_result(fail("bad"))))
            trace.append("after")
            return 100

        result = await run_async(workflow())
        self.assertEqual(result, Fail("bad"))
        self.assertEqual(trace, ["before"])

    async def test_delay_to_thread_success_result_is_unwrapped(self):
        @do
        def workflow() -> Do[int, str]:
            a = yield from step(delay_to_thread(lambda: success(4)))
            b = yield from step(delay_to_thread(lambda: success(6)))
            return a + b

        result = await run_async(workflow())
        self.assertEqual(result, Success(10))

    async def test_delay_to_thread_fail_result_short_circuits(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            trace.append("before")
            yield from step(delay_to_thread(lambda: fail("thread-fail")))
            trace.append("after")
            return 1

        result = await run_async(workflow())
        self.assertEqual(result, Fail("thread-fail"))
        self.assertEqual(trace, ["before"])

    async def test_lift_effect_lifts_plain_aff_value_into_success(self):
        @do
        def workflow() -> Do[int, str]:
            a = yield from step(lift_effect(aff_pure(10)))
            b = yield from step(lift_effect(aff_delay(lambda: _async_value(15))))
            return a + b

        result = await run_async(workflow())
        self.assertEqual(result, Success(25))

    async def test_lift_effect_never_short_circuits_on_value(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            x = yield from step(lift_effect(aff_delay(lambda: _async_value(1))))
            trace.append(f"x={x}")
            y = yield from step(pure_success(2))
            return x + y

        result = await run_async(workflow())
        self.assertEqual(result, Success(3))
        self.assertEqual(trace, ["x=1"])

    async def test_python_exception_from_underlying_aff_is_not_converted_to_fail_by_run_async(self):
        @do
        def workflow() -> Do[int, str]:
            yield from step(lift_effect(aff_delay(lambda: _async_raise(ValueError("boom")))))
            return 1

        with self.assertRaises(ValueError) as ctx:
            await run_async(workflow())

        self.assertEqual(str(ctx.exception), "boom")

    async def test_python_exception_from_underlying_aff_is_captured_by_run_safe_async(self):
        @do
        def workflow() -> Do[int, str]:
            yield from step(lift_effect(aff_delay(lambda: _async_raise(ValueError("boom")))))
            return 1

        result = await run_safe_async(workflow())
        self.assertIsInstance(result, Fail)
        self.assertIsInstance(result.error if isinstance(result, Fail) else None, ValueError)
        self.assertEqual(str(result.error if isinstance(result, Fail) else None), "boom")

    async def test_fail_value_is_not_an_exception_and_is_returned_by_run_async(self):
        @do
        def workflow() -> Do[int, str]:
            yield from step(pure_fail("domain-error"))
            return 1

        result = await run_async(workflow())
        self.assertEqual(result, Fail("domain-error"))

    async def test_short_circuit_skips_all_subsequent_steps(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            trace.append("s1")
            x = yield from step(pure_success(1))
            trace.append(f"s2:{x}")
            yield from step(pure_fail("stop"))
            trace.append("s3")
            yield from step(pure_success(999))
            return 1000

        result = await run_async(workflow())
        self.assertEqual(result, Fail("stop"))
        self.assertEqual(trace, ["s1", "s2:1"])

    async def test_nested_aff_result_generator_success(self):
        @do
        def inner() -> Do[int, str]:
            x = yield from step(pure_success(4))
            y = yield from step(pure_success(5))
            return x * y

        @do
        def outer() -> Do[int, str]:
            a = yield from step(pure_success(2))
            b = yield from step(inner())
            return a + b

        result = await run_async(outer())
        self.assertEqual(result, Success(22))

    async def test_nested_aff_result_generator_propagates_fail(self):
        trace: list[str] = []

        @do
        def inner() -> Do[int, str]:
            trace.append("inner:start")
            yield from step(pure_fail("inner-fail"))
            trace.append("inner:after")
            return 1

        @do
        def outer() -> Do[int, str]:
            trace.append("outer:start")
            x = yield from step(pure_success(10))
            y = yield from step(inner())
            trace.append("outer:after-inner")
            return x + y

        result = await run_async(outer())
        self.assertEqual(result, Fail("inner-fail"))
        self.assertEqual(trace, ["outer:start", "inner:start"])

    async def test_nested_aff_result_generator_fail_bubbles_through_multiple_levels(self):
        trace: list[str] = []

        @do
        def leaf() -> Do[int, str]:
            trace.append("leaf")
            yield from step(pure_fail("leaf-fail"))
            trace.append("leaf-after")
            return 1

        @do
        def middle() -> Do[int, str]:
            trace.append("middle")
            value = yield from step(leaf())
            trace.append(f"middle-after:{value}")
            return value + 1

        @do
        def outer() -> Do[int, str]:
            trace.append("outer")
            value = yield from step(middle())
            trace.append(f"outer-after:{value}")
            return value + 1

        result = await run_async(outer())
        self.assertEqual(result, Fail("leaf-fail"))
        self.assertEqual(trace, ["outer", "middle", "leaf"])

    async def test_nested_success_then_fail_in_outer(self):
        trace: list[str] = []

        @do
        def inner() -> Do[int, str]:
            trace.append("inner")
            yield from step(pure_success(0))
            return 7

        @do
        def outer() -> Do[int, str]:
            trace.append("outer:start")
            x = yield from step(inner())
            trace.append(f"outer:got:{x}")
            yield from step(pure_fail("outer-fail"))
            trace.append("outer:after")
            return x

        result = await run_async(outer())
        self.assertEqual(result, Fail("outer-fail"))
        self.assertEqual(trace, ["outer:start", "inner", "outer:got:7"])

    async def test_can_mix_lifted_aff_and_aff_result_steps(self):
        @do
        def workflow()  -> Do[int, str]:
            a = yield from step(lift_effect(aff_delay(lambda: _async_value(3))))
            b = yield from step(pure_success(4))
            c = yield from step(delay(lambda: _async_result(success(5))))
            return a + b + c

        result = await run_async(workflow())
        self.assertEqual(result, Success(12))

    async def test_domain_fail_inside_delay_is_distinct_from_python_exception(self):
        @do
        def workflow_fail() -> Do[int, str]:
            yield from step(delay(lambda: _async_result(fail("bad-result"))))
            return 1

        @do
        def workflow_exc() -> Do[int, str]:
            yield from step(lift_effect(aff_delay(lambda: _async_raise(RuntimeError("bad-exc")))))
            return 1

        result_fail = await run_async(workflow_fail())
        self.assertEqual(result_fail, Fail("bad-result"))

        with self.assertRaises(RuntimeError) as ctx:
            await run_async(workflow_exc())
        self.assertEqual(str(ctx.exception), "bad-exc")

    async def test_short_circuit_from_nested_generator_prevents_outer_followup_effects(self):
        trace: list[str] = []

        @do
        def inner() -> Do[int, str]:
            trace.append("inner:before-fail")
            yield from step(pure_fail("inner-stop"))
            trace.append("inner:after-fail")
            return 1

        @do
        def outer() -> Do[int, str]:
            trace.append("outer:before-inner")
            yield from step(inner())
            trace.append("outer:after-inner")
            yield from step(lift_effect(aff_delay(lambda: _async_trace_and_return(trace, "plain-aff-ran", 10))))
            return 99

        result = await run_async(outer())
        self.assertEqual(result, Fail("inner-stop"))
        self.assertEqual(trace, ["outer:before-inner", "inner:before-fail"])

    async def test_multiple_successful_steps_preserve_order(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            a = yield from step(delay(lambda: _async_trace_and_result(trace, "first", Success(1))))
            b = yield from step(delay(lambda: _async_trace_and_result(trace, "second", Success(2))))
            c = yield from step(lift_effect(aff_delay(lambda: _async_trace_and_return(trace, "third", 3))))
            return a + b + c

        result = await run_async(workflow())
        self.assertEqual(result, Success(6))
        self.assertEqual(trace, ["first", "second", "third"])

    async def test_fail_after_lifted_plain_aff_discards_computed_value(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            x = yield from step(lift_effect(aff_delay(lambda: _async_trace_and_return(trace, "compute-x", 10))))
            trace.append(f"x={x}")
            yield from step(pure_fail("stop"))
            trace.append("after-stop")
            return x + 1

        result = await run_async(workflow())
        self.assertEqual(result, Fail("stop"))
        self.assertEqual(trace, ["compute-x", "x=10"])

    async def test_nested_generator_return_value_is_unwrapped_not_success_object(self):
        @do
        def inner() -> Do[int, str]:
            yield from step(pure_success(0))
            return 50

        @do
        def outer() -> Do[int, str]:
            x = yield from step(inner())
            self.assertIsInstance(x, int)
            return x + 2

        result = await run_async(outer())
        self.assertEqual(result, Success(52))

    async def test_step_accepts_prebuilt_aff_result_gen_based_instance(self):
        def inner_workflow() -> Do[int, str]:
            value = yield from step(pure_success(9))
            return value + 1

        inner = AffResultGenBased(inner_workflow)

        @do
        def outer() -> Do[int, str]:
            result = yield from step(inner)
            return result * 3

        actual = await run_async(outer())
        self.assertEqual(actual, Success(30))

    async def test_run_safe_async_wraps_successful_transformer_result(self):
        @do
        def workflow() -> Do[int, str]:
            x = yield from step(pure_success(11))
            return x * 2

        result = await run_safe_async(workflow())
        self.assertEqual(result, Success(Success(22)))

    async def test_run_safe_async_wraps_domain_fail_as_success_of_fail(self):
        @do
        def workflow() -> Do[int, str]:
            yield from step(pure_fail("domain-stop"))
            return 1

        result = await run_safe_async(workflow())
        self.assertEqual(result, Success(Fail("domain-stop")))

    async def test_error_value_can_be_any_object_not_only_exception(self):
        marker: dict[str, int | str] = {"code": 400, "message": "bad input"}

        @do
        def workflow() -> Do[int, dict[str, int | str]]:
            yield from step(pure_fail(marker))
            return 1

        result = await run_async(workflow())
        self.assertEqual(result, Fail(marker))

    async def test_success_values_can_themselves_contain_fail_objects_without_short_circuit(self):
        payload = Fail("just-data")

        @do
        def workflow() -> Do[Fail[str], str]:
            value = yield from step(pure_success(payload))
            return value

        result = await run_async(workflow())
        self.assertEqual(result, Success(payload))

    async def test_successful_nested_then_plain_fail_result_from_delay(self):
        trace: list[str] = []

        @do
        def inner() -> Do[int, str]:
            trace.append("inner")
            yield from step(pure_success(0))
            return 5

        @do
        def outer() -> Do[int, str]:
            x = yield from step(inner())
            trace.append(f"got:{x}")
            yield from step(delay(lambda: _async_result(fail("late-fail"))))
            trace.append("after")
            return x + 1

        result = await run_async(outer())
        self.assertEqual(result, Fail("late-fail"))
        self.assertEqual(trace, ["inner", "got:5"])

    async def test_retry_retries_on_fail_result_and_stops_after_first_success(self):
        trace: list[str] = []
        state = {"attempt": 0}

        async def flaky_result():
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            if state["attempt"] < 3:
                return Fail(f"err-{state['attempt']}")
            return Success(10)

        @do
        def workflow() -> Do[int, str]:
            value = yield from step(
                retry(
                    flaky_result,
                    total_attempts=5,
                    retry_on_result=lambda r: isinstance(r, Fail),
                    step_name="flaky_result_step",
                )
            )
            trace.append(f"unwrapped:{value}")
            return value + 5

        result = await run_async(workflow())

        self.assertEqual(result, Success(15))
        self.assertEqual(state["attempt"], 3)
        self.assertEqual(
            trace,
            [
                "attempt:1",
                "attempt:2",
                "attempt:3",
                "unwrapped:10",
            ]
        )

    async def test_retry_retries_on_exception_and_then_returns_success_result(self):
        trace: list[str] = []
        state = {"attempt": 0}

        async def flaky():
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            if state["attempt"] < 3:
                raise ValueError(f"boom-{state['attempt']}")
            return success(8)

        @do
        def workflow()  -> Do[int, str]:
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

        self.assertEqual(result, Success(16))
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

    async def test_retry_result_predicate_can_retry_on_success_payload_and_later_short_circuit_on_fail(self):
        trace: list[str] = []
        state = {"attempt": 0}

        async def tricky():
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            if state["attempt"] == 1:
                return Success(0)   # retry because predicate says so
            if state["attempt"] == 2:
                return Fail("terminal-fail")  # retry stops here only if predicate says False
            return Success(99)

        @do
        def workflow() -> Do[int, str]:
            value = yield from step(
                retry(
                    tricky,
                    total_attempts=5,
                    retry_on_result=lambda r: r == Success(0),
                    step_name="tricky-result-retry",
                )
            )
            trace.append(f"value:{value}")
            return value

        result = await run_async(workflow())

        self.assertEqual(result, Fail("terminal-fail"))
        self.assertEqual(state["attempt"], 2)
        self.assertEqual(trace, ["attempt:1", "attempt:2"])

    async def test_retry_can_retry_on_success_result_payload_multiple_times_before_terminal_success(self):
        trace: list[str] = []
        state = {"attempt": 0}

        async def flaky():
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            if state["attempt"] < 4:
                return success(0)
            return success(9)

        @do
        def workflow() -> Do[int, str]:
            value = yield from step(
                retry(
                    flaky,
                    total_attempts=5,
                    retry_on_result=lambda r: r == Success(0),
                    step_name="success-payload-retry",
                )
            )
            trace.append(f"value:{value}")
            return value + 1

        result = await run_async(workflow())

        self.assertEqual(result, Success(10))
        self.assertEqual(state["attempt"], 4)
        self.assertEqual(
            trace,
            [
                "attempt:1",
                "attempt:2",
                "attempt:3",
                "attempt:4",
                "value:9",
           ]
        ) 

    async def test_retry_can_mix_exception_retries_and_result_retries_before_success(self):
        trace: list[str] = []
        state = {"attempt": 0}

        async def tricky():
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            if state["attempt"] == 1:
                raise ValueError("boom-1")
            if state["attempt"] in (2, 3):
                return Fail(f"soft-{state['attempt']}")
            return Success(11)

        @do
        def workflow() -> Do[int, str]:
            value = yield from step(
                retry(
                    tricky,
                    total_attempts=5,
                    retry_on_result=lambda r: isinstance(r, Fail),
                    retry_on_exceptions=(ValueError,),
                    step_name="mixed-retry",
                )
            )
            trace.append(f"value:{value}")
            return value * 2

        result = await run_async(workflow())

        self.assertEqual(result, Success(22))
        self.assertEqual(state["attempt"], 4)
        self.assertEqual(
            trace,
            [
                "attempt:1",
                "attempt:2",
                "attempt:3",
                "attempt:4",
                "value:11",
            ]
        )


if __name__ == '__main__':
    unittest.main()

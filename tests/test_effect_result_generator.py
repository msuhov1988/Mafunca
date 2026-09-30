import unittest
from typing import Never

from mafunca.result.build import Success, Fail, success, fail, Result
from mafunca.eff.build import delay as eff_delay, pure as eff_pure
from mafunca.eff_trans.build import (
    EffResultGenBased,
    pure_success,
    pure_fail,
    pure_result,
    lift_effect,
    delay,
    retry,
    step,
    do,
    Do
)
from mafunca.effect_runners_gen_based import run, run_safe


class TestEffResultGenBased(unittest.TestCase):

    def test_run_returns_success_on_plain_happy_path(self):
        @do
        def workflow() -> Do[int, Never]:
            a = yield from step(pure_success(10))
            b = yield from step(pure_success(20))
            return a + b

        result = run(workflow())
        self.assertEqual(result, Success(30))

    def test_final_return_is_wrapped_into_success(self):
        @do
        def workflow() -> Do[int, Never]:
            yield from step(pure_success(0))
            return 123

        result = run(workflow())
        self.assertEqual(result, Success(123))

    def test_pure_fail_short_circuits_immediately(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            trace.append("before")
            yield from step(pure_fail("boom"))
            trace.append("after")
            return 999

        result = run(workflow())
        self.assertEqual(result, Fail("boom"))
        self.assertEqual(trace, ["before"])

    def test_pure_result_success_is_unwrapped(self):
        @do
        def workflow() -> Do[int, Never]:            
            value = yield from step(pure_result(success(7)))
            return value * 6

        result = run(workflow())
        self.assertEqual(result, Success(42))

    def test_pure_result_fail_short_circuits(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            trace.append("start")
            yield from step(pure_result(fail("err")))
            trace.append("unreachable")
            return 1

        result = run(workflow())
        self.assertEqual(result, Fail("err"))
        self.assertEqual(trace, ["start"])

    def test_delay_success_result_is_unwrapped(self):
        @do
        def workflow() -> Do[int, Never]:
            a = yield from step(delay(lambda: success(5)))
            b = yield from step(delay(lambda: success(8)))
            return a * b

        result = run(workflow())
        self.assertEqual(result, Success(40))

    def test_delay_fail_result_short_circuits(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            trace.append("before")
            yield from step(delay(lambda: fail("bad")))
            trace.append("after")
            return 100

        result = run(workflow())
        self.assertEqual(result, Fail("bad"))
        self.assertEqual(trace, ["before"])

    def test_lift_effect_lifts_plain_eff_value_into_success(self):
        @do
        def workflow() -> Do[int, Never]:
            a = yield from step(lift_effect(eff_pure(10)))
            b = yield from step(lift_effect(eff_delay(lambda: 15)))
            return a + b

        result = run(workflow())
        self.assertEqual(result, Success(25))

    def test_lift_effect_never_short_circuits_on_value(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, Never]:
            x = yield from step(lift_effect(eff_delay(lambda: 1)))
            trace.append(f"x={x}")
            y = yield from step(pure_success(2))
            return x + y

        result = run(workflow())
        self.assertEqual(result, Success(3))
        self.assertEqual(trace, ["x=1"])

    def test_python_exception_from_underlying_eff_is_not_converted_to_fail_by_run(self):
        @do
        def workflow() -> Do[int, Never]:
            yield from step(lift_effect(eff_delay(lambda: (_ for _ in ()).throw(ValueError("boom")))))
            return 1

        with self.assertRaises(ValueError) as ctx:
            run(workflow())

        self.assertEqual(str(ctx.exception), "boom")

    def test_python_exception_from_underlying_eff_is_captured_by_run_safe(self):
        @do
        def workflow() -> Do[int, Never]:
            yield from step(lift_effect(eff_delay(lambda: (_ for _ in ()).throw(ValueError("boom")))))
            return 1

        result = run_safe(workflow())
        self.assertIsInstance(result, Fail)
        self.assertIsInstance(result.error if isinstance(result, Fail) else None, ValueError)
        self.assertEqual(str(result.error if isinstance(result, Fail) else None), "boom")

    def test_fail_value_is_not_an_exception_and_is_returned_by_run(self):
        @do
        def workflow() -> Do[int, str]:
            yield from step(pure_fail("domain-error"))
            return 1

        result = run(workflow())
        self.assertEqual(result, Fail("domain-error"))

    def test_short_circuit_skips_all_subsequent_steps(self):
        trace: list[str] = []
        Do[int, str]
        @do
        def workflow() -> Do[int, str]:
            trace.append("s1")
            x = yield from step(pure_success(1))
            trace.append(f"s2:{x}")
            _ = yield from step(pure_fail("stop"))
            trace.append("s3")
            yield from step(pure_success(999))
            return 1000

        result = run(workflow())
        self.assertEqual(result, Fail("stop"))
        self.assertEqual(trace, ["s1", "s2:1"])

    def test_nested_eff_result_generator_success(self):
        @do
        def inner() -> Do[int, Never]:
            x = yield from step(pure_success(4))
            y = yield from step(pure_success(5))
            return x * y

        @do
        def outer() -> Do[int, int]:
            a = yield from step(pure_success(2))
            b = yield from step(inner())
            return a + b

        result = run(outer())
        self.assertEqual(result, Success(22))

    def test_nested_eff_result_generator_propagates_fail(self):
        trace: list[str] = []

        @do
        def inner() -> Do[int, str]:
            trace.append("inner:start")
            yield from step(pure_fail("inner-fail"))
            trace.append("inner:after")
            return 1

        @do
        def outer()  -> Do[int, str]:
            trace.append("outer:start")
            x = yield from step(pure_success(10))
            y = yield from step(inner())
            trace.append("outer:after-inner")
            return x + y

        result = run(outer())
        self.assertEqual(result, Fail("inner-fail"))
        self.assertEqual(trace, ["outer:start", "inner:start"])

    def test_nested_eff_result_generator_fail_bubbles_through_multiple_levels(self):
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

        result = run(outer())
        self.assertEqual(result, Fail("leaf-fail"))
        self.assertEqual(trace, ["outer", "middle", "leaf"])

    def test_nested_success_then_fail_in_outer(self):
        trace: list[str] = []

        @do
        def inner() -> Do[int, Never]:
            trace.append("inner")
            yield from step(pure_success(1))
            return 7

        @do
        def outer() -> Do[int, str]:
            trace.append("outer:start")
            x = yield from step(inner())
            trace.append(f"outer:got:{x}")
            yield from step(pure_fail("outer-fail"))
            trace.append("outer:after")
            return x

        result = run(outer())
        self.assertEqual(result, Fail("outer-fail"))
        self.assertEqual(trace, ["outer:start", "inner", "outer:got:7"])

    def test_can_mix_lifted_eff_and_eff_result_steps(self):
        @do
        def workflow() -> Do[int, int]:
            a = yield from step(lift_effect(eff_delay(lambda: 3)))
            b = yield from step(pure_success(4))
            c = yield from step(delay(lambda: success(5)))
            return a + b + c

        result = run(workflow())
        self.assertEqual(result, Success(12))

    def test_domain_fail_inside_delay_is_distinct_from_python_exception(self):
        @do
        def workflow_fail() -> Do[int, str]:
            yield from step(delay(lambda: fail("bad-result")))
            return 1

        @do
        def workflow_exc() -> Do[int, Never]:
            yield from step(lift_effect(eff_delay(lambda: (_ for _ in ()).throw(RuntimeError("bad-exc")))))
            return 1

        result_fail = run(workflow_fail())
        self.assertEqual(result_fail, Fail("bad-result"))

        with self.assertRaises(RuntimeError) as ctx:
            run(workflow_exc())
        self.assertEqual(str(ctx.exception), "bad-exc")

    def test_short_circuit_from_nested_generator_prevents_outer_followup_effects(self):
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
            yield from step(lift_effect(eff_delay(lambda: trace.append("plain-eff-ran") or 10)))
            return 99

        result = run(outer())
        self.assertEqual(result, Fail("inner-stop"))
        self.assertEqual(trace, ["outer:before-inner", "inner:before-fail"])

    def test_multiple_successful_steps_preserve_order(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            a = yield from step(delay(lambda: trace.append("first") or success(1)))
            b = yield from step(delay(lambda: trace.append("second") or success(2)))
            c = yield from step(lift_effect(eff_delay(lambda: trace.append("third") or 3)))
            return a + b + c

        result = run(workflow())
        self.assertEqual(result, Success(6))
        self.assertEqual(trace, ["first", "second", "third"])

    def test_fail_after_lifted_plain_effect_discards_computed_value(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int, str]:
            x = yield from step(lift_effect(eff_delay(lambda: trace.append("compute-x") or 10)))
            trace.append(f"x={x}")
            yield from step(pure_fail("stop"))
            trace.append("after-stop")
            return x + 1

        result = run(workflow())
        self.assertEqual(result, Fail("stop"))
        self.assertEqual(trace, ["compute-x", "x=10"])

    def test_nested_generator_return_value_is_unwrapped_not_success_object(self):
        @do
        def inner() -> Do[int, Never]:
            yield from step(pure_success(1))
            return 50

        @do
        def outer() -> Do[int, Never]:
            x = yield from step(inner())
            self.assertIsInstance(x, int)
            return x + 2

        result = run(outer())
        self.assertEqual(result, Success(52))

    def test_step_accepts_prebuilt_eff_result_gen_based_instance(self):
        def inner_workflow() -> Do[int, Never]:
            value = yield from step(pure_success(9))
            return value + 1

        inner = EffResultGenBased(inner_workflow)

        @do
        def outer() -> Do[int, Never]:
            result = yield from step(inner)
            return result * 3

        actual = run(outer())
        self.assertEqual(actual, Success(30))

    def test_run_safe_wraps_successful_transformer_result(self):
        @do
        def workflow() -> Do[int, Never]:
            x = yield from step(pure_success(11))
            return x * 2

        result = run_safe(workflow())
        self.assertEqual(result, Success(Success(22)))

    def test_run_safe_wraps_domain_fail_as_success_of_fail(self):
        @do
        def workflow() -> Do[int, str]:
            yield from step(pure_fail("domain-stop"))
            return 1

        result = run_safe(workflow())
        self.assertEqual(result, Success(Fail("domain-stop")))

    def test_error_value_can_be_any_object_not_only_exception(self):
        marker: dict[str, int | str] = {"code": 400, "message": "bad input"}

        @do
        def workflow() -> Do[int, dict[str, int | str]]:
            yield from step(pure_fail(marker))
            return 1

        result = run(workflow())
        self.assertEqual(result, Fail(marker))

    def test_success_values_can_themselves_contain_fail_objects_without_short_circuit(self):
        payload = fail("just-data")

        @do
        def workflow() -> Do[Result[Never, str], Never]:
            value = yield from step(pure_success(payload))
            return value

        result = run(workflow())
        self.assertEqual(result, Success(payload))

    def test_successful_nested_then_plain_fail_result_from_delay(self):
        trace: list[str] = []

        @do
        def inner() -> Do[int, Never]:
            trace.append("inner")
            _ = yield from step(pure_success(0))
            return 5

        @do
        def outer() -> Do[int, str]:
            x = yield from step(inner())
            trace.append(f"got:{x}")
            yield from step(delay(lambda: fail("late-fail")))
            trace.append("after")
            return x + 1

        result = run(outer())
        self.assertEqual(result, Fail("late-fail"))
        self.assertEqual(trace, ["inner", "got:5"])


    def test_retry_retries_on_fail_result_and_short_circuit_stops_after_first_success(self):
        trace: list[str] = []
        state = {"attempt": 0}

        def flaky_result() -> Result[int, str]:
            state["attempt"] += 1
            trace.append(f"attempt:{state['attempt']}")
            if state["attempt"] < 3:
                return fail(f"err-{state['attempt']}")
            return success(10)

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

        result = run(workflow())

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


if __name__ == '__main__':
    unittest.main()

import unittest

from mafunca.eff.build import pure, delay, do, step, Do
from mafunca.eff.direct import fmap, bind, catch_bind
from mafunca.result.build import Success, Fail

from mafunca.effect_runners_gen_based import run, run_safe


class TestEffGenBased(unittest.TestCase):

    def test_run_simple_generator_happy_path(self):
        @do
        def workflow() -> Do[int]:
            a = yield from step(pure(10))
            b = yield from step(delay(lambda: 20))
            return a + b

        result = run(workflow())
        self.assertEqual(result, 30)

    def test_run_nested_generator_workflow(self):
        @do
        def inner() -> Do[int]:
            x = yield from step(delay(lambda: 3))
            y = yield from step(pure(4))
            return x * y

        @do
        def outer() -> Do[int]:
            a = yield from step(pure(2))
            b = yield from step(inner())
            c = yield from step(delay(lambda: 5))
            return a + b + c

        result = run(outer())
        self.assertEqual(result, 19)

    def test_run_exception_inside_effect_can_be_caught_in_generator_via_catch_bind(self):
        effect = catch_bind(
            delay(lambda: 1 / 0),
            ZeroDivisionError,
            lambda exc: pure(f"caught: {exc.__class__.__name__}")
        )

        @do
        def workflow() -> Do[float | str]:
            value = yield from step(effect)
            return value

        result = run(workflow())
        self.assertEqual(result, "caught: ZeroDivisionError")

    def test_run_exception_thrown_into_generator_and_recovered_by_generator_try_except(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[int | None]:
            trace.append("start")
            try:
                yield from step(delay(lambda: (_ for _ in ()).throw(ValueError("boom"))))
            except ValueError as exc:
                trace.append(f"handled:{exc}")
                recovered = yield from step(pure(100))
                return recovered + 1
            finally:
                trace.append("finally")

        result = run(workflow())
        self.assertEqual(result, 101)
        self.assertEqual(trace, ["start", "handled:boom", "finally"])

    def test_run_multiple_failures_before_success_inside_generator(self):
        state = {"n": 0}

        def flaky():
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

        result = run(workflow())        
        self.assertEqual(result, 52)
        self.assertEqual(state["n"], 3)      

    def test_run_generator_finally_executes_when_effect_raises_and_is_not_caught(self):
        trace: list[str] = []

        @do
        def workflow() -> Do[None]:
            try:
                yield from step(delay(lambda: (_ for _ in ()).throw(ValueError("boom"))))
            finally:
                trace.append("generator-finally")

        with self.assertRaises(ValueError):
            run(workflow())

        self.assertEqual(trace, ["generator-finally"])

    def test_run_safe_wraps_exception_into_fail(self):
        @do
        def workflow() -> Do[int]:
            a = yield from step(pure(1))
            b = yield from step(delay(lambda: (_ for _ in ()).throw(ValueError("bad"))))
            return a + b

        result = run_safe(workflow())
        self.assertIsInstance(result, Fail)
        self.assertIsInstance(result.error if isinstance(result, Fail) else None, ValueError)
        self.assertEqual(str(result.error if isinstance(result, Fail) else None), "bad")

    def test_run_safe_does_not_wrap_base_exception(self):
        @do
        def workflow() -> Do[int]:
            yield from step(delay(lambda: (_ for _ in ()).throw(KeyboardInterrupt())))
            return 1

        with self.assertRaises(KeyboardInterrupt):
            run_safe(workflow())

    def test_run_safe_success_path(self):
        @do
        def workflow() -> Do[int]:
            x = yield from step(delay(lambda: 5))
            y = yield from step(delay(lambda: 6))
            return x * y

        result = run_safe(workflow())
        self.assertEqual(result, Success(30))        

    def test_generator_can_yield_mapped_and_bound_effects(self):
        effect = bind(
            fmap(delay(lambda: 10), lambda x: x + 2),
            lambda x: pure(x * 3)
        )

        @do
        def workflow() -> Do[int]:
            value = yield from step(effect)
            return value - 1

        result = run(workflow())
        self.assertEqual(result, 35)

    def test_nested_generator_exception_propagates_to_outer_generator(self):
        trace: list[str] = []

        @do
        def inner() -> Do[None]:
            trace.append("inner:start")
            yield from step(delay(lambda: (_ for _ in ()).throw(ValueError("inner-boom"))))

        @do
        def outer() -> Do[None | str]:
            trace.append("outer:start")
            try:
                yield from step(inner())
            except ValueError as exc:
                trace.append(f"outer:caught:{exc}")
                return "recovered"

        result = run(outer())
        self.assertEqual(result, "recovered")
        self.assertEqual(trace, ["outer:start", "inner:start", "outer:caught:inner-boom"])

    def test_generator_close_happens_for_nested_workflow_finally(self):
        trace: list[str] = []

        @do
        def inner() -> Do[None]:
            try:
                yield from step(pure(1))
                yield from step(delay(lambda: (_ for _ in ()).throw(ValueError("boom"))))
            finally:
                trace.append("inner-finally")

        @do
        def outer() -> Do[None]:
            try:
                yield from step(inner())
            finally:
                trace.append("outer-finally")

        with self.assertRaises(ValueError):
            run(outer())

        self.assertEqual(trace, ["inner-finally", "outer-finally"])  

    def test_nested_generators_outer_catches_inner_error_both_finally_execute_and_outer_recovers(self):
        trace: list[str] = []

        @do
        def inner() -> Do[None]:
            trace.append("inner:start")
            try:
                yield from step(pure(1))
                yield from step(delay(lambda: (_ for _ in ()).throw(RuntimeError("boom"))))
            finally:
                trace.append("inner:finally")

        @do
        def outer() -> Do[int | None]:
            trace.append("outer:start")
            try:
                yield from step(inner())
            except RuntimeError as exc:
                trace.append(f"outer:except:{exc}")
                fallback = yield from step(delay(lambda: 20))
                return fallback + 1
            finally:
                trace.append("outer:finally")

        result = run(outer())

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

    def test_three_level_nested_generators_exception_rethrown_transformed_and_all_finally_execute(self):
        trace: list[str] = []

        @do
        def leaf() -> Do[None]:
            trace.append("leaf:start")
            try:
                yield from step(delay(lambda: (_ for _ in ()).throw(ValueError("leaf-error"))))
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
                val = yield from step(delay(lambda: 100))
                return val + 23
            finally:
                trace.append("outer:finally")

        result = run(outer())

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

    def test_chained_exceptions(self):
        glb: list [str] = []

        @do
        def chained_exceptions() -> Do[None]:
            nonlocal glb
            try:
                yield from step(delay(lambda: 1 / 0))
            except ZeroDivisionError:                
                glb.append("zero-div")
                try:
                    raise ValueError("boom")  
                except ValueError:
                    glb.append("value-err")
                    norm = yield from step(delay(lambda: "normal"))
                    glb.append(norm)
                    raise TypeError("err")

            finally:
                glb.append("finally")

        with self.assertRaises(TypeError):
            run(chained_exceptions())        
        self.assertEqual(glb, ["zero-div", "value-err", "normal", "finally"])  
  


if __name__ == '__main__':
    unittest.main()

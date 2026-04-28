import unittest

from mafunca.triple import Left, Nothing
from mafunca.common.exceptions import MonadError
from mafunca.resilient_sync import of, from_func, insist
from mafunca.common.resilient_support import Report, Uncaught


class TestResilientSync(unittest.TestCase):

    def test_ordinary_chains1(self):
        rp = of(1).run()
        self.assertEqual(rp.result, 1)

        rp = of(1).run(rebuild=True)
        self.assertEqual(rp.result, rp.last_success)

        rp = of(1).chain(lambda v: v + 5).run(rebuild=True)
        self.assertEqual(rp.result, rp.last_success)

        rp = of(10).chain(lambda v: v + 5).chain(lambda v: of(v ** 2)).run()
        self.assertIsInstance(rp, Report)
        self.assertEqual(rp.chain_from_failure, None)
        self.assertEqual(rp.faulty, None)
        self.assertEqual(rp.result, 225)
        self.assertEqual(rp.last_success, None)

    def test_ordinary_chains2(self):
        rp = of(10).chain(lambda v: from_func(lambda: v + 5)).chain(lambda v: v ** 2).run()
        self.assertIsInstance(rp, Report)
        self.assertEqual(rp.chain_from_failure, None)
        self.assertEqual(rp.faulty, None)
        self.assertEqual(rp.result, 225)
        self.assertEqual(rp.last_success, None)

    def test_short_circuit(self):
        rp = of(Left('error')).chain(lambda v: from_func(lambda: v + 5)).run()
        self.assertEqual(rp.result.unfold(), 'error')
        self.assertEqual(rp.last_success, None)
        rp = of(10).chain(lambda _: of(Nothing())).chain(lambda v: v ** 2).run()
        self.assertIsInstance(rp.result, Nothing)
        self.assertEqual(rp.last_success, None)

    def test_catching_errors_uncaught(self):
        def raiser():
            raise TypeError('error')

        resilient = from_func(raiser).chain(lambda v: v + 1).chain(lambda v: v + 1)
        rp = resilient.run(rebuild=True)
        self.assertEqual(rp.chain_from_failure is resilient, True)
        self.assertEqual(rp.faulty is raiser, True)

        rp = from_func(raiser).chain(lambda v: v + 1).chain(lambda v: v ** 2).run()
        err = rp.result
        self.assertIsInstance(err, Uncaught)
        self.assertIsInstance(err.error, TypeError)
        with self.assertRaises(TypeError):
            err.throw()

    def test_catching_errors_caught(self):
        def raiser():
            raise TypeError('error')

        rp = from_func(raiser).chain(lambda v: v + 1).catch(lambda _: 100).run()
        self.assertEqual(rp.chain_from_failure, None)
        self.assertEqual(rp.faulty, None)
        self.assertEqual(rp.result, 100)

    def test_catching_errors_no_effect1(self):
        rp = from_func(lambda: 1).chain(lambda v: v + 1).catch(lambda _: 100).chain(lambda v: v + 1).run()
        self.assertEqual(rp.result, 3)

    def test_catching_errors_no_effect2(self):
        rp = from_func(lambda: 1).chain(lambda _: Left(0)).catch(lambda _: 100).chain(lambda v: v + 1).run()
        self.assertIsInstance(rp.result, Left)

    def test_ensure_normal(self):
        g = 0

        def plus():
            nonlocal g
            g += 1

        rp = of(10).chain(lambda v: v + 5).chain(lambda v: v ** 2).ensure(plus).run()
        self.assertEqual(rp.result, 225)
        self.assertEqual(g, 1)

    def test_ensure_uncaught(self):
        g = 0

        def raiser():
            raise TypeError('error')

        def plus():
            nonlocal g
            g += 1

        rp = from_func(raiser).chain(lambda v: v + 5).chain(lambda v: v ** 2).ensure(plus).run()
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(g, 1)

    def test_ensure_bad_triple(self):
        g = 0

        def plus():
            nonlocal g
            g += 1

        rp = from_func(lambda: Nothing()).ensure(plus).chain(lambda v: v + 1).run()
        self.assertIsInstance(rp.result, Nothing)
        self.assertEqual(g, 1)

    def test_no_coroutine(self):
        async def coroutine1():
            return 10

        async def coroutine2(v):
            return v

        with self.assertRaises(MonadError):
            _ = from_func(coroutine1)

        with self.assertRaises(MonadError):
            _ = of(10).chain(lambda _: from_func(coroutine1)).run()

        with self.assertRaises(MonadError):
            _ = of(10).chain(coroutine2)

    def test_nested_ordinary_chain(self):
        def inner_chain(val: int):
            return from_func(lambda: val ** 2).chain(lambda v: v + 1).chain(lambda v: v + 1)

        rp = of(5).chain(lambda v: v + 5).chain(inner_chain).run()
        self.assertEqual(rp.result, 102)

    def test_nested_short_circuit(self):

        def inner_chain(val: int):
            return of(val).chain(lambda _: Left('error')).chain(lambda v: v + 1)

        rp = of(5).chain(lambda v: v + 5).chain(inner_chain).chain(lambda v: v + 1).run()
        self.assertIsInstance(rp.result, Left)

    def test_nested_uncaught_errors(self):
        def raiser():
            raise TypeError('error')

        def inner_chain(val: int):
            return from_func(raiser).chain(lambda _: val + 1).chain(lambda v: v + 1)

        rp = of(5).chain(lambda v: v + 5).chain(inner_chain).run()
        self.assertIsInstance(rp.result, Uncaught)

    def test_nested_caught_errors(self):
        def raiser():
            raise TypeError('error')

        def inner_chain(val: int):
            return from_func(raiser).chain(lambda _: val + 1)

        rp = of(5).chain(lambda v: v + 5).chain(inner_chain).catch(lambda _: 0).run()
        self.assertEqual(rp.result, 0)

    def test_nested_caught_ensure(self):
        def raiser():
            raise TypeError('error')

        g = 0

        def plus():
            nonlocal g
            g += 1

        def inner_chain(val: int):
            return from_func(raiser).chain(lambda _: val + 1)

        rp = of(5).chain(lambda v: v + 5).chain(inner_chain).ensure(plus).run()
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(g, 1)

    def test_retry_simple(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        resilient = of(10).chain(plus)
        rp = resilient.run(rebuild=True)
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(rp.last_success, 10)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(rp.last_success, 10)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 100)
        self.assertEqual(rp.last_success, 100)

        g = -2
        self.assertEqual(insist(resilient, attempts=5).result, 100)

    def test_retry_simple_short_circuit(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                return Nothing()
            return val ** 2

        resilient = of(10).chain(plus)
        rp = resilient.run(rebuild=True)
        self.assertIsInstance(rp.result, Nothing)
        self.assertEqual(rp.last_success, 10)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertIsInstance(rp.result, Nothing)
        self.assertEqual(rp.last_success, 10)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 100)
        self.assertEqual(rp.last_success, 100)

        g = -2
        self.assertEqual(insist(resilient, attempts=5).result, 100)

    def test_retry_simple_caught(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        resilient = of(10).chain(plus).catch(lambda _: 0)
        self.assertEqual(resilient.run(rebuild=True).result, 0)
        self.assertEqual(resilient.run(rebuild=True).last_success, 0)

        g = 0
        self.assertEqual(insist(resilient, attempts=1).result, 0)

    def test_retry_simple_ensure(self):
        a, b = 0, 0

        def plus(val):
            nonlocal a
            a += 1
            if a < 3:
                raise TypeError('error')
            return val ** 2

        def ensure_plus():
            nonlocal b
            b += 1

        resilient = of(10).chain(plus).ensure(ensure_plus)
        rp = resilient.run(rebuild=True)
        rp = rp.chain_from_failure.run(rebuild=True)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 100)
        self.assertEqual(b, 3)

        a, b = -2, 0
        self.assertEqual(insist(resilient, attempts=5).result, 100)
        self.assertEqual(b, 5)

    def test_retry_nested(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        def inner(o):
            return of(o).chain(plus).chain(lambda v: from_func(lambda: v + 1))

        resilient = of(10).chain(lambda v: v + 10).chain(inner).chain(lambda v: v + 1)
        rp = resilient.run(rebuild=True)
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(rp.last_success, 20)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(rp.last_success, 20)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 402)
        self.assertEqual(rp.last_success, 402)

        g = -2
        self.assertEqual(insist(resilient, attempts=5).result, 402)

    def test_retry_nested_short_circuit(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                return Nothing()
            return val ** 2

        def inner(o):
            return of(o).chain(plus).chain(lambda v: from_func(lambda: v + 1))

        resilient = of(10).chain(lambda v: v + 10).chain(inner).chain(lambda v: v + 1)
        rp = resilient.run(rebuild=True)
        self.assertIsInstance(rp.result, Nothing)
        self.assertEqual(rp.last_success, 20)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertIsInstance(rp.result, Nothing)
        self.assertEqual(rp.last_success, 20)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 402)
        self.assertEqual(rp.last_success, 402)

        g = -2
        self.assertEqual(insist(resilient, attempts=5).result, 402)

    def test_retry_nested_caught(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        def inner(o):
            return of(o).chain(plus).catch(lambda _: 0)

        resilient = of(10).chain(lambda v: v + 10).chain(inner).chain(lambda v: v + 1)
        rp = resilient.run(rebuild=True)
        self.assertEqual(rp.result, 1)
        self.assertEqual(rp.last_success, 1)

        g = 0
        self.assertEqual(insist(resilient, attempts=1).result, 1)
        self.assertEqual(insist(resilient, attempts=1).last_success, 1)

    def test_retry_nested_ensure(self):
        a, b = 0, 0

        def plus(val):
            nonlocal a
            a += 1
            if a < 3:
                raise TypeError('error')
            return val ** 2

        def ensure_plus():
            nonlocal b
            b += 1

        def inner(o):
            return of(o).chain(plus)

        resilient = of(10).chain(lambda v: v + 10).chain(inner).chain(lambda v: v + 1).ensure(ensure_plus)
        rp = resilient.run(rebuild=True)
        rp = rp.chain_from_failure.run(rebuild=True)
        rp = rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 401)
        self.assertEqual(b, 3)

        a, b = -2, 0
        self.assertEqual(insist(resilient, attempts=5).result, 401)
        self.assertEqual(b, 5)

    def test_faulty_extraction(self):
        def failure(arg):
            return arg / 0

        def failure_prime():
            return 10 / 0

        rp = of(10).chain(failure).chain(lambda v: v + 1).run(rebuild=True)
        self.assertIs(rp.faulty, failure)
        self.assertEqual(rp.last_success, 10)

        rp = from_func(failure_prime).chain(failure).run(rebuild=True)
        self.assertIs(rp.faulty, failure_prime)

    def test_catch_breaks_restored_chain(self):
        def failure1(arg):
            return arg / 0

        def failure2(arg):
            return arg / 0

        rp = of(10).chain(failure1).chain(lambda v: v + 1).catch(lambda _: 0).chain(failure2).run(rebuild=True)
        self.assertIs(rp.faulty, failure2)
        self.assertEqual(rp.last_success, 0)

    def test_single_side_effect1(self):
        kit, g = [], 0

        def raiser(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError("it's too early")
            return val

        def side_effect(val):
            nonlocal kit
            kit.append("side_effect")
            return val ** 2

        resilient = of(10).chain(lambda v: of(v * 2).chain(side_effect).chain(raiser)).chain(lambda v: v - 100)
        rp = insist(resilient, 1)
        self.assertEqual(rp.last_success, 400)
        rp = insist(rp.chain_from_failure, 2)
        self.assertEqual(rp.result, 300)
        self.assertEqual(rp.last_success, 300)
        self.assertEqual(kit, ["side_effect"])

    def test_single_side_effect2(self):
        kit, g = [], 0

        def side_effect_level2(val):
            nonlocal kit
            kit.append(2)
            return val + 1

        def raiser_level2(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError("it's too early")
            return val + 1

        def side_effect_level1(val):
            nonlocal kit
            kit.append(1)
            return val + 1

        def raiser_level1(val):
            nonlocal g
            g += 1
            if g < 5:
                raise TypeError("it's too early")
            return val + 1

        def side_effect_level0(val):
            nonlocal kit
            kit.append(0)
            return val ** 2

        def level2(val):
            return from_func(lambda: val + 1).chain(side_effect_level2).chain(raiser_level2).chain(lambda v: v)

        def level1(val):
            return (
                from_func(lambda: val + 1)
                .chain(level2)
                .chain(side_effect_level1)
                .chain(raiser_level1)
                .chain(lambda v: v)
            )

        resilient = of(0).chain(level1).chain(side_effect_level0)
        rp = insist(resilient, 3)
        self.assertEqual(rp.last_success, 5)
        rp = insist(rp.chain_from_failure, 10)
        self.assertEqual(rp.result, 36)
        self.assertEqual(rp.last_success, 36)
        self.assertEqual(kit, [2, 1, 0])

    def test_partial_execution_steps_violation(self):
        rp = of(100).run(steps=0)
        self.assertEqual(rp.result, 100)
        resilient = of(0).chain(lambda v: v + 1)
        rp = resilient.run(steps=-1)
        self.assertEqual(rp.result, 0)
        rp = resilient.run(steps=0)
        self.assertEqual(rp.result, 0)
        rp = resilient.run(steps=1)
        self.assertEqual(rp.result, 0)
        rp = resilient.run(steps=-10)
        self.assertEqual(rp.chain_from_failure, None)

    def test_flat_partial_execution(self):
        resilient = of(0).chain(lambda v: v + 1).chain(lambda v: v + 1).chain(lambda v: v + 10)
        rp = resilient.run(steps=1)
        self.assertEqual(rp.result, 0)

        rp = resilient.run(steps=2)
        self.assertEqual(rp.result, 1)

        rp = resilient.run(steps=3)
        self.assertEqual(rp.result, 2)

        rp = resilient.run(steps=4)
        self.assertEqual(rp.result, 12)

        rp = resilient.run(steps=50)
        self.assertEqual(rp.result, 12)

    def test_nested_partial_execution(self):
        def level(val):
            return from_func(lambda: val + 1).chain(lambda v: v * 2).chain(lambda v: v * 2)

        resilient = of(1).chain(level).chain(lambda v: v + 10).chain(lambda v: v + 10).chain(lambda v: v + 10)
        rp = resilient.run(steps=1)
        self.assertEqual(rp.result, 1)

        rp = resilient.run(steps=3)
        self.assertEqual(rp.result, 18)

        rp = resilient.run(steps=4)
        self.assertEqual(rp.result, 28)

    def test_errors_flat_partial_execution(self):
        g = 0

        def raiser(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError("it's too early")
            return val * 2

        resilient = of(0).chain(lambda v: v + 1).chain(raiser).chain(lambda v: v + 10)
        rp = resilient.run(rebuild=True, steps=3)
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(rp.last_success, 1)

        rp = insist(rp.chain_from_failure, 2)
        self.assertEqual(rp.result, 2)

    def test_errors_nested_partial_execution(self):
        g = 0

        def raiser(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError("it's too early")
            return val * 2

        def level(val):
            return from_func(lambda: val + 1).chain(raiser).chain(lambda v: v * 2)

        resilient = of(1).chain(level).chain(lambda v: v + 10).chain(lambda v: v + 10).chain(lambda v: v + 10)
        rp = resilient.run(rebuild=True, steps=3)
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(rp.last_success, 2)

        rp = insist(rp.chain_from_failure, 2)
        self.assertEqual(rp.result, 18)


if __name__ == '__main__':
    unittest.main()

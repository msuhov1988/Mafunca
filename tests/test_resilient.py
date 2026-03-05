import unittest
import asyncio

from mafunca.triple import Left, Nothing
from mafunca.resilient import of, unit, insist
from mafunca.common.resilient_support import Report, Uncaught


async def get_five():
    return 5


async def plus_five(val):
    return val + 5


class TestResilient(unittest.IsolatedAsyncioTestCase):

    async def test_ordinary_chains1(self):
        rp = await of(10).chain(plus_five).chain(lambda v: of(v ** 2)).run()
        self.assertIsInstance(rp, Report)
        self.assertEqual(rp.chain_from_failure, None)
        self.assertEqual(rp.faulty, None)
        self.assertEqual(rp.result, 225)

    async def test_ordinary_chains2(self):
        rp = await of(0).chain(lambda v: unit(get_five)).chain(plus_five).run()
        self.assertIsInstance(rp, Report)
        self.assertEqual(rp.chain_from_failure, None)
        self.assertEqual(rp.faulty, None)
        self.assertEqual(rp.result, 10)

    async def test_short_circuit(self):
        rp = await of(Left('error')).chain(plus_five).run()
        self.assertEqual(rp.result.unfold(), 'error')
        rp = await unit(get_five).chain(lambda _: of(Nothing())).chain(lambda v: v ** 2).run()
        self.assertIsInstance(rp.result, Nothing)

    async def test_catching_errors_uncaught(self):
        async def raiser():
            raise TypeError('error')

        rp = await unit(raiser).chain(lambda v: v + 1).chain(plus_five).run()
        err = rp.result
        self.assertIsInstance(err, Uncaught)
        self.assertIsInstance(err.error, TypeError)
        with self.assertRaises(TypeError):
            err.throw()

    async def test_catching_errors_caught(self):
        async def raiser():
            raise TypeError('error')

        rp = await unit(raiser).chain(plus_five).catch(lambda _: 100).run()
        self.assertEqual(rp.chain_from_failure, None)
        self.assertEqual(rp.faulty, None)
        self.assertEqual(rp.result, 100)

    async def test_catching_errors_no_effect1(self):
        async def catcher(_):
            return 100

        rp = await unit(lambda: 1).chain(plus_five).catch(catcher).chain(lambda v: v + 1).run()
        self.assertEqual(rp.result, 7)

    async def test_catching_errors_no_effect2(self):
        async def catcher(_):
            return 100

        rp = await unit(lambda: 1).chain(lambda _: Left(0)).catch(catcher).chain(plus_five).run()
        self.assertIsInstance(rp.result, Left)

    async def test_ensure_normal(self):
        g = 0

        def plus():
            nonlocal g
            g += 1

        rp = await of(10).chain(plus_five).chain(lambda v: v ** 2).ensure(plus).run()
        self.assertEqual(rp.result, 225)
        self.assertEqual(g, 1)

    async def test_ensure_uncaught(self):
        g = 0

        async def raiser():
            raise TypeError('error')

        async def plus():
            nonlocal g
            g += 1

        rp = await unit(raiser).chain(plus_five).chain(lambda v: v ** 2).ensure(plus).run()
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(g, 1)

    async def test_ensure_bad_triple(self):
        g = 0

        async def plus():
            nonlocal g
            g += 1

        rp = await unit(lambda: Nothing()).ensure(plus).chain(plus_five).run()
        self.assertIsInstance(rp.result, Nothing)
        self.assertEqual(g, 1)

    async def test_nested_ordinary_chain(self):
        def inner_chain(val: int):
            return unit(lambda: val ** 2).chain(lambda v: v + 1).chain(lambda v: v + 1)

        rp = await of(5).chain(plus_five).chain(inner_chain).run()
        self.assertEqual(rp.result, 102)

    async def test_nested_short_circuit(self):
        def inner_chain(val: int):
            return of(val).chain(lambda _: Left('error')).chain(lambda v: v + 1)

        rp = await unit(get_five).chain(plus_five).chain(inner_chain).run()
        self.assertIsInstance(rp.result, Left)

    async def test_nested_uncaught_errors(self):
        async def raiser():
            raise TypeError('error')

        def inner_chain(val: int):
            return unit(raiser).chain(lambda _: val + 1).chain(lambda v: v + 1)

        rp = await unit(get_five).chain(plus_five).chain(inner_chain).run()
        self.assertIsInstance(rp.result, Uncaught)

    async def test_nested_caught_errors(self):
        async def raiser():
            raise TypeError('error')

        def inner_chain(val: int):
            return unit(raiser).chain(lambda _: val + 1).catch(lambda _: 0)

        rp = await of(5).chain(plus_five).chain(inner_chain).run()
        self.assertEqual(rp.result, 0)

    async def test_nested_caught_ensure(self):
        async def raiser():
            raise TypeError('error')

        g = 0

        def plus():
            nonlocal g
            g += 1

        def inner_chain(val: int):
            return unit(raiser).chain(lambda _: val + 1).ensure(plus)

        rp = await unit(get_five).chain(plus_five).chain(inner_chain).run()
        self.assertIsInstance(rp.result, Uncaught)
        self.assertEqual(g, 1)

    async def test_retry_simple(self):
        g = 0

        async def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        resilient = of(10).chain(plus)
        rp = await resilient.run(rebuild=True)
        self.assertIsInstance(rp.result, Uncaught)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertIsInstance(rp.result, Uncaught)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 100)

        g = -2
        rp = await insist(resilient, attempts=5)
        self.assertEqual(rp.result, 100)

    async def test_retry_simple_short_circuit(self):
        g = 0

        async def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                return Nothing()
            return val ** 2

        resilient = of(10).chain(plus)
        rp = await resilient.run(rebuild=True)
        self.assertIsInstance(rp.result, Nothing)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertIsInstance(rp.result, Nothing)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 100)

        g = -2
        rp = await insist(resilient, attempts=5)
        self.assertEqual(rp.result, 100)

    async def test_retry_simple_caught(self):
        g = 0

        async def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        resilient = of(10).chain(plus).catch(lambda _: 0)
        rp = await resilient.run(rebuild=True)
        self.assertEqual(rp.result, 0)

        g = 0
        rp = await insist(resilient, attempts=1)
        self.assertEqual(rp.result, 0)

    async def test_retry_simple_ensure(self):
        a, b = 0, 0

        async def plus(val):
            nonlocal a
            a += 1
            if a < 3:
                raise TypeError('error')
            return val ** 2

        async def ensure_plus():
            nonlocal b
            b += 1

        resilient = of(10).chain(plus).ensure(ensure_plus)
        rp = await resilient.run(rebuild=True)
        rp = await rp.chain_from_failure.run(rebuild=True)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 100)
        self.assertEqual(b, 3)

        a, b = -2, 0
        rp = await insist(resilient, attempts=5)
        self.assertEqual(rp.result, 100)
        self.assertEqual(b, 5)

    async def test_retry_nested(self):
        g = 0

        async def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        def inner(o):
            return of(o).chain(plus).chain(lambda v: unit(lambda: v + 1))

        resilient = of(5).chain(plus_five).chain(inner).chain(lambda v: v + 1)
        rp = await resilient.run(rebuild=True)
        self.assertIsInstance(rp.result, Uncaught)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertIsInstance(rp.result, Uncaught)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 102)

        g = -2
        rp = await insist(resilient, attempts=5)
        self.assertEqual(rp.result, 102)

    async def test_retry_nested_short_circuit(self):
        g = 0

        async def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                return Nothing()
            return val ** 2

        def inner(o):
            return of(o).chain(plus).chain(lambda v: unit(lambda: v + 1))

        resilient = of(5).chain(plus_five).chain(inner).chain(lambda v: v + 1)
        rp = await resilient.run(rebuild=True)
        self.assertIsInstance(rp.result, Nothing)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertIsInstance(rp.result, Nothing)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 102)

        g = -2
        rp = await insist(resilient, attempts=5)
        self.assertEqual(rp.result, 102)

    async def test_retry_nested_caught(self):
        g = 0

        async def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        def inner(o):
            return of(o).chain(plus).catch(lambda _: 0)

        resilient = of(10).chain(plus_five).chain(inner).chain(lambda v: v + 1)
        rp = await resilient.run(rebuild=True)
        self.assertEqual(rp.result, 1)

        g = 0
        rp = await insist(resilient, attempts=1)
        self.assertEqual(rp.result, 1)

    async def test_retry_nested_ensure(self):
        a, b = 0, 0

        async def plus(val):
            nonlocal a
            a += 1
            if a < 3:
                raise TypeError('error')
            return val ** 2

        async def ensure_plus():
            nonlocal b
            b += 1

        def inner(o):
            return of(o).chain(plus).ensure(ensure_plus)

        resilient = unit(get_five).chain(plus_five).chain(inner).chain(lambda v: v + 1)
        rp = await resilient.run(rebuild=True)
        rp = await rp.chain_from_failure.run(rebuild=True)
        rp = await rp.chain_from_failure.run(rebuild=True)
        self.assertEqual(rp.result, 101)
        self.assertEqual(b, 3)

        a, b = -2, 0
        rp = await insist(resilient, attempts=5)
        self.assertEqual(rp.result, 101)
        self.assertEqual(b, 5)

    async def test_delay(self):
        async def waiter(val):
            await asyncio.sleep(1)
            return val ** 2

        resilient = unit(get_five).chain(waiter)
        with self.assertRaises(TimeoutError):
            await resilient.run(delay=0.5)

        rp = await insist(resilient, attempts=2, delay_for_attempt=0.5)
        self.assertEqual(rp.chain_from_failure, resilient)

    async def test_faulty_extraction(self):
        async def failure(arg):
            return arg / 0

        async def failure_prime():
            return 10 / 0

        rp = await of(10).chain(failure).chain(lambda v: v + 1).run(rebuild=True)
        self.assertIs(rp.faulty, failure)

        rp = await unit(failure_prime).chain(failure).run(rebuild=True)
        self.assertIs(rp.faulty, failure_prime)

    async def test_catch_breaks_restored_chain(self):
        async def failure1(arg):
            return arg / 0

        async def failure2(arg):
            return arg / 0

        rp = await of(10).chain(failure1).chain(lambda v: v + 1).catch(lambda _: 0).chain(failure2).run(rebuild=True)
        self.assertIs(rp.faulty, failure2)


if __name__ == '__main__':
    unittest.main()

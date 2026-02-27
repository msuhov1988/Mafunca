import unittest
import asyncio

from mafunca.triple import Left, Nothing
from mafunca.common.exceptions import MonadError
from mafunca.eff import Eff


class TestEff(unittest.IsolatedAsyncioTestCase):
    async def test_map(self):
        async def plus(x):
            return x + 1

        eff = Eff.of(10).map(lambda x: x + 1)
        self.assertEqual(await eff.run(), 11)

        eff = Eff.of(10).map(plus)
        self.assertEqual(await eff.run(), 11)

    async def test_bind(self):
        async def multiply(x):
            return Eff.of(x * 3)

        eff = Eff.of(5).bind(lambda x: Eff.of(x * 3))
        self.assertEqual(await eff.run(), 15)

        eff = Eff.of(5).bind(multiply)
        self.assertEqual(await eff.run(), 15)

    async def test_short_circuit(self):
        eff = Eff(lambda: Left('err')).map(lambda x: x + 10)
        result = await eff.run()
        self.assertIsInstance(result, Left)
        self.assertEqual(result.unfold(), 'err')

        eff = Eff(lambda: Nothing()).map(lambda x: x + 10)
        result = await eff.run()
        self.assertIsInstance(result, Nothing)

        eff = Eff(lambda: Left("err")).bind(lambda x: Eff.of(x + 1))
        result = await eff.run()
        self.assertIsInstance(result, Left)
        self.assertEqual(result.unfold(), "err")

        eff = Eff(lambda: Nothing()).bind(lambda x: Eff.of(x + 1))
        result = await eff.run()
        self.assertIsInstance(result, Nothing)

    async def test_violation(self):
        eff = Eff.of(1).map(lambda x: Eff.of(x))
        with self.assertRaises(MonadError):
            await eff.run()

        eff = Eff.of(1).bind(lambda x: x + 1)
        with self.assertRaises(MonadError):
            await eff.run()

    async def test_to_thread_violation(self):
        async def violate_sync(x):
            return x + 1

        eff = Eff.of(1)
        with self.assertRaises(MonadError):
            eff.map_to_thread(violate_sync)

        eff = Eff.of(1)
        with self.assertRaises(MonadError):
            eff.bind_to_thread(violate_sync)

        eff = Eff.of(1).map_to_thread(lambda x: Eff.of(x))
        with self.assertRaises(MonadError):
            await eff.run()

        eff = Eff.of(1).bind_to_thread(lambda x: x + 1)
        with self.assertRaises(MonadError):
            await eff.run()

        eff = Eff.of(5).map_to_thread(lambda x: x * 2)
        self.assertEqual(await eff.run(), 10)

        eff = Eff.of(5).bind_to_thread(lambda x: Eff.of(x * 3))
        self.assertEqual(await eff.run(), 15)

    async def test_catch(self):
        async def raiser():
            raise TypeError("error")

        async def catcher(_):
            return 10

        eff = Eff(raiser).catch(lambda e: 10)
        self.assertEqual(await eff.run(), 10)

        eff = Eff(raiser).catch(catcher)
        self.assertEqual(await eff.run(), 10)

        eff = Eff.of(10).map(lambda x: x + 1).catch(lambda e: 0)
        self.assertEqual(await eff.run(), 11)

    async def test_catch_monad_error(self):
        def raises():
            raise MonadError("Eff", "test", "err")

        eff = Eff(raises).catch(lambda e: 42)
        with self.assertRaises(MonadError):
            await eff.run()

    async def test_ensure_sync(self):
        log = []

        def ensure_fn():
            log.append('called')

        def raiser():
            raise TypeError("error")

        wrapped = Eff.of(0).map(lambda _: raiser()).ensure(ensure_fn)
        with self.assertRaises(TypeError):
            await wrapped.run()
        self.assertEqual(log, ['called'])

    async def test_ensure_async(self):
        log = []

        async def eff():
            return 10

        async def ensure_fn():
            log.append('called')

        async def raiser(_):
            raise TypeError("error")

        wrapped = Eff(eff).map(raiser).ensure(ensure_fn)
        with self.assertRaises(TypeError):
            await wrapped.run()
        self.assertEqual(log, ['called'])

    async def test_to_task_requires_async(self):
        eff = Eff.of(2)
        with self.assertRaises(MonadError):
            eff.to_task()

        async def eff_async():
            return 3

        eff2 = Eff(eff_async)
        task = eff2.to_task()
        self.assertTrue(asyncio.isfuture(task))
        result = await task
        self.assertEqual(result, 3)

    async def test_run_delay(self):
        async def fn():
            await asyncio.sleep(2)
            return 1

        eff = Eff(fn)
        with self.assertRaises(TimeoutError):
            await eff.run(delay=1)

        val = await eff.run(delay=3)
        self.assertEqual(val, 1)

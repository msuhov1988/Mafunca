import unittest
import asyncio
from time import sleep

from mafunca.common.exceptions import MonadError
from mafunca.side_async import AsyncSide
from mafunca.side_async import side_run
from mafunca.side_async import side_safe_run
from mafunca.side_async import side_rebuild_run
from mafunca.side_async import insist


class TestAsyncSide(unittest.IsolatedAsyncioTestCase):
    async def test_pure_chain(self):
        eff = AsyncSide.pure(0).map(lambda x: x + 1).map(lambda x: x + 1)
        self.assertEqual(await side_run(eff), 2)

        res = await side_safe_run(eff)
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(0), 2)

        report = await side_rebuild_run(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully, 2)

    async def test_basic_chain(self):
        def plus(x):

            async def inner():
                return x + 1

            return AsyncSide.effect(inner)

        def multiply(x):
            async def inner():
                return x * 3

            return AsyncSide.effect(inner)

        eff = AsyncSide.pure(10).map(lambda x: x + 1)
        self.assertEqual(await side_run(eff), 11)

        res = await side_safe_run(eff)
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(0), 11)

        report = await side_rebuild_run(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully, 11)

        eff = AsyncSide.pure(10).bind(plus)
        self.assertEqual(await side_run(eff), 11)

        res = await side_safe_run(eff)
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(0), 11)

        report = await side_rebuild_run(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully, 11)

        eff = AsyncSide.pure(5).bind(multiply)
        self.assertEqual(await side_run(eff), 15)

    async def test_catch_errors(self):
        def raiser():
            raise TypeError        
        
        eff = AsyncSide.pure(0).map(lambda _: raiser()).bind(lambda x: AsyncSide.pure(lambda: x + 1))
        res = await side_safe_run(eff)

        self.assertTrue(res.is_error)
        self.assertIsInstance(res.error, TypeError)

        report = await side_rebuild_run(eff)
        self.assertFalse(report.completed_successfully)
        self.assertEqual(report.last_successfully, 0)
        self.assertIsInstance(report.exception, TypeError)

    async def test_bind_violation(self):
        eff = AsyncSide.pure(10).bind(lambda x: x + 1)
        with self.assertRaises(MonadError):
            await side_run(eff)
        with self.assertRaises(MonadError):
            await side_safe_run(eff)
        with self.assertRaises(MonadError):
            await side_rebuild_run(eff)

    async def test_func_type_violation(self):
        async def plus_map(x):
            return x + 1

        async def plus_bind(x):
            return AsyncSide.pure(x + 1)

        async def plus_thread():
            return 1

        with self.assertRaises(MonadError):
            AsyncSide.pure(10).map(plus_map)
        with self.assertRaises(MonadError):
            AsyncSide.pure(10).bind(plus_bind)  # noqa
        with self.assertRaises(MonadError):
            AsyncSide.effect_to_thread(plus_thread)

    async def test_delay(self):
        async def fn():
            await asyncio.sleep(0.3)
            return 1

        eff = AsyncSide.effect(fn, timeout=0.1)
        with self.assertRaises(TimeoutError):
            await side_run(eff)

        res = await side_safe_run(eff)
        self.assertTrue(res.is_error)
        self.assertIsInstance(res.error, TimeoutError)

        res = await side_rebuild_run(eff)
        self.assertFalse(res.completed_successfully)
        self.assertIsInstance(res.exception, TimeoutError)

        eff = AsyncSide.effect(fn, timeout=0.6)
        val = await side_run(eff)
        self.assertEqual(val, 1)

    async def test_delay_to_thread(self):
        def fn():
            sleep(0.3)
            return 1

        eff = AsyncSide.effect_to_thread(fn, timeout=0.1)
        with self.assertRaises(TimeoutError):
            await side_run(eff)

        res = await side_safe_run(eff)
        self.assertTrue(res.is_error)
        self.assertIsInstance(res.error, TimeoutError)

        res = await side_rebuild_run(eff)
        self.assertFalse(res.completed_successfully)
        self.assertIsInstance(res.exception, TimeoutError)

        eff = AsyncSide.effect_to_thread(fn, timeout=0.6)
        val = await side_run(eff)
        self.assertEqual(val, 1)

    async def test_cancellation(self):
        async def first():
            await asyncio.sleep(0.1)
            return 1

        def second(val):
            async def inner():
                await asyncio.sleep(0.1)
                return val + 1

            return AsyncSide.effect(inner)

        eff = AsyncSide.effect(first).bind(second)

        task1 = asyncio.create_task(side_run(eff))
        await asyncio.sleep(0)
        task1.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task1

        task2 = asyncio.create_task(side_safe_run(eff))
        await asyncio.sleep(0)
        task2.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task2

        task3 = asyncio.create_task(side_rebuild_run(eff))
        await asyncio.sleep(0)
        task3.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task3

    async def test_rebuild_errors(self):
        async def raiser():
            raise TypeError('error')

        eff = AsyncSide.effect(raiser).map(lambda v: v + 1).map(lambda v: v + 1)
        rp = await side_rebuild_run(eff)
        self.assertIs(rp.faulty, raiser)

        err = rp.exception
        self.assertIsInstance(err, TypeError)
        with self.assertRaises(TypeError):
            raise err

    async def test_double_nested_chain(self):
        def inner_chain(val: int):
            async def inner():
                return val ** 2

            return AsyncSide.effect(inner).map(lambda v: v + 1).map(lambda v: v + 1)

        eff = AsyncSide.pure(5).map(lambda v: v + 5).bind(inner_chain)
        self.assertEqual(await side_run(eff), 102)

        res = await side_safe_run(eff)
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(0), 102)

        report = await side_rebuild_run(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully, 102)

    async def test_double_nested_chain_errors(self):
        async def raiser():
            raise TypeError('error')

        def inner_chain(val: int):
            return AsyncSide.effect(raiser).map(lambda _: val + 1).map(lambda v: v + 1)

        eff = AsyncSide.pure(5).map(lambda v: v + 5).bind(inner_chain)
        with self.assertRaises(TypeError):
            await side_run(eff)

        res = await side_safe_run(eff)
        self.assertTrue(res.is_error)
        self.assertIsInstance(res.error, TypeError)

        rp = await side_rebuild_run(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 10)
        self.assertIsInstance(rp.exception, TypeError)

    async def test_triple_nested_chain_errors(self):
        async def raiser():
            raise TypeError('error')

        def inner_second_chain(val: int):
            return AsyncSide.effect(raiser).map(lambda _: val + 1)

        def inner_first_chain(val: int):
            async def inner():
                return val ** 2

            return AsyncSide.effect(inner).bind(inner_second_chain)

        eff = AsyncSide.pure(5).map(lambda v: v + 5).bind(inner_first_chain)
        rp = await side_rebuild_run(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 100)
        self.assertIsInstance(rp.exception, TypeError)

    async def test_retry_simple_from_effect(self):
        g = 0

        def plus(val):
            async def inner():
                nonlocal g
                g += 1
                if g < 3:
                    raise TypeError('error')
                return val ** 2

            return AsyncSide.effect(inner)

        eff = AsyncSide.pure(10).bind(plus)
        rp = await side_rebuild_run(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 10)

        rp = await side_rebuild_run(rp.remainder)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, None)

        rp = await side_rebuild_run(rp.remainder)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 100)

        g = -2
        rp = await insist(eff, attempts=5)
        self.assertEqual(rp.last_successfully, 100)

    async def test_retry_simple_from_continuation(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        eff = AsyncSide.pure(10).map(plus)
        rp = await side_rebuild_run(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 10)

        rp = await side_rebuild_run(rp.remainder)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 10)

        rp = await side_rebuild_run(rp.remainder)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 100)

        g = -2
        rp = await insist(eff, attempts=5)
        self.assertEqual(rp.last_successfully, 100)

    async def test_retry_nested_from_effect(self):
        g = 0

        def plus(val):
            async def plus_inner():
                nonlocal g
                g += 1
                if g < 3:
                    raise TypeError('error')
                return val ** 2

            return AsyncSide.effect(plus_inner)

        def inner(o):
            return AsyncSide.pure(o).bind(plus).bind(lambda v: AsyncSide.pure(v + 1))

        eff = AsyncSide.pure(10).map(lambda v: v + 10).bind(inner).map(lambda v: v + 1)
        rp = await side_rebuild_run(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 20)

        rp = await side_rebuild_run(rp.remainder)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, None)

        rp = await side_rebuild_run(rp.remainder)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 402)

        g = -2
        rp = await insist(eff, attempts=5)
        self.assertEqual(rp.last_successfully, 402)

    async def test_retry_nested_from_continuation(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        def inner(o):
            return AsyncSide.pure(o).map(plus).bind(lambda v: AsyncSide.pure(v + 1))

        eff = AsyncSide.pure(10).map(lambda v: v + 10).bind(inner).map(lambda v: v + 1)
        rp = await side_rebuild_run(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 20)

        rp = await side_rebuild_run(rp.remainder)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 20)

        rp = await side_rebuild_run(rp.remainder)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 402)

        g = -2
        rp = await insist(eff, attempts=5)
        self.assertEqual(rp.last_successfully, 402)

    async def test_side_effect1(self):
        kit, g = [], 0

        def raiser(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError("it's too early")
            return val - 100

        def side_effect(val):
            nonlocal kit
            kit.append("side_effect")
            return val ** 2

        eff = AsyncSide.pure(10).bind(lambda v: AsyncSide.pure(v * 2).map(side_effect).map(raiser))
        rp = await insist(eff, 1)
        self.assertEqual(rp.last_successfully, 400)
        rp = await insist(rp.remainder, 2)
        self.assertEqual(rp.last_successfully, 300)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(kit, ["side_effect"])

    async def test_side_effect2(self):
        kit, g = [], 0

        def side_effect_level2(val):
            nonlocal kit
            kit.append(2)
            return val + 1

        def raiser_level2(val):
            async def inner():
                nonlocal g
                g += 1
                if g < 3:
                    raise TypeError("it's too early")
                return val + 1

            return AsyncSide.effect(inner)

        def side_effect_level1(val):
            nonlocal kit
            kit.append(1)
            return val + 1

        def raiser_level1(val):
            async def inner():
                nonlocal g
                g += 1
                if g < 5:
                    raise TypeError("it's too early")
                return val + 1

            return AsyncSide.effect(inner)

        def side_effect_level0(val):
            nonlocal kit
            kit.append(0)
            return val ** 2

        def level2(val):
            return AsyncSide.pure(val + 1).map(side_effect_level2).bind(raiser_level2).map(lambda v: v)

        def level1(val):
            return (
                AsyncSide.pure(val + 1)
                .bind(level2)
                .map(side_effect_level1)
                .bind(raiser_level1)
                .map(lambda v: v)
            )

        eff = AsyncSide.pure(0).bind(level1).map(side_effect_level0)
        rp = await insist(eff, 3)
        self.assertEqual(rp.last_successfully, 5)
        rp = await insist(rp.remainder, 10)
        self.assertEqual(rp.last_successfully, 36)
        self.assertEqual(kit, [2, 1, 0])


if __name__ == '__main__':
    unittest.main()

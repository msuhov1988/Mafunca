import unittest

from mafunca.common.exceptions import MonadError
from mafunca.result import Ok, Err
from mafunca.side import Side, SideT
from mafunca.side_runners import run, run_safe, run_rebuild, insist


class TestSide(unittest.TestCase):
    def test_pure_chain(self):
        eff = Side.pure(0).map(lambda x: x + 1).map(lambda x: x + 1)
        self.assertEqual(run(eff), 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(0), 2)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully, 2)

    def test_basic_chain(self):
        eff = Side.pure(0).map(lambda x: x + 1).bind(lambda x: Side.effect(lambda: x + 1))
        self.assertEqual(run(eff), 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(0), 2)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully, 2)

        eff = Side.effect(lambda: 0).map(lambda x: x + 1).bind(lambda x: Side.pure(x + 1))
        self.assertEqual(run(eff), 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(0), 2)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully, 2)

    def test_catch_errors(self):
        def raiser():
            raise TypeError

        eff = Side.pure(0).map(lambda _: raiser()).bind(lambda x: Side.effect(lambda: x + 1))
        res = run_safe(eff)
        self.assertTrue(res.is_error)
        self.assertIsInstance(res.error, TypeError)

        report = run_rebuild(eff)
        self.assertFalse(report.completed_successfully)
        self.assertEqual(report.last_successfully, 0)
        self.assertIsInstance(report.exception, TypeError)

    def test_contract_violation(self):
        eff = Side.effect(lambda: 10).bind(lambda x: x + 1)
        with self.assertRaises(MonadError):
            run(eff)
        with self.assertRaises(MonadError):
            run_safe(eff)
        with self.assertRaises(MonadError):
            run_rebuild(eff)

    def test_func_type_violation(self):
        async def plus_map(x):
            return x + 1

        async def plus_bind(x):
            return Side.pure(x + 1)

        async def plus_prime():
            return 1

        with self.assertRaises(MonadError):
            Side.pure(10).map(plus_map)
        with self.assertRaises(MonadError):
            Side.pure(10).bind(plus_bind)  # noqa
        with self.assertRaises(MonadError):
            Side.effect(plus_prime).map(lambda x: x + 1)

    def test_rebuild_errors(self):
        def raiser():
            raise TypeError('error')

        eff = Side.effect(raiser).map(lambda v: v + 1).map(lambda v: v + 1)
        rp = run_rebuild(eff)
        self.assertIs(rp.faulty, raiser)

        err = rp.exception
        self.assertIsInstance(err, TypeError)
        with self.assertRaises(TypeError):
            raise err

    def test_double_nested_chain(self):
        def inner_chain(val: int):
            return Side.effect(lambda: val ** 2).map(lambda v: v + 1).map(lambda v: v + 1)

        eff = Side.pure(5).map(lambda v: v + 5).bind(inner_chain)
        self.assertEqual(run(eff), 102)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertEqual(res.get_or_else(0), 102)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully, 102)

    def test_double_nested_chain_errors(self):
        def raiser():
            raise TypeError('error')

        def inner_chain(val: int):
            return Side.effect(raiser).map(lambda _: val + 1).map(lambda v: v + 1)

        eff = Side.pure(5).map(lambda v: v + 5).bind(inner_chain)
        with self.assertRaises(TypeError):
            run(eff)

        res = run_safe(eff)
        self.assertTrue(res.is_error)
        self.assertIsInstance(res.error, TypeError)

        rp = run_rebuild(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 10)
        self.assertIsInstance(rp.exception, TypeError)

    def test_triple_nested_chain_errors(self):
        def raiser():
            raise TypeError('error')

        def inner_second_chain(val: int):
            return Side.effect(raiser).map(lambda _: val + 1)

        def inner_first_chain(val: int):
            return Side.effect(lambda: val ** 2).bind(inner_second_chain)

        eff = Side.pure(5).map(lambda v: v + 5).bind(inner_first_chain)
        rp = run_rebuild(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 100)
        self.assertIsInstance(rp.exception, TypeError)

    def test_retry_simple_from_effect(self):
        g = 0

        def plus(val):
            def inner():
                nonlocal g
                g += 1
                if g < 3:
                    raise TypeError('error')
                return val ** 2

            return Side.effect(inner)

        eff = Side.pure(10).bind(plus)
        rp = run_rebuild(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 10)

        rp = run_rebuild(rp.remainder)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, None)

        rp = run_rebuild(rp.remainder)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 100)

        g = -2
        self.assertEqual(insist(eff, attempts=5).last_successfully, 100)

    def test_retry_simple_from_continuation(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        eff = Side.pure(10).map(plus)
        rp = run_rebuild(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 10)

        rp = run_rebuild(rp.remainder)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 10)

        rp = run_rebuild(rp.remainder)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 100)

        g = -2
        self.assertEqual(insist(eff, attempts=5).last_successfully, 100)

    def test_retry_nested_from_effect(self):
        g = 0

        def plus(val):
            def plus_inner():
                nonlocal g
                g += 1
                if g < 3:
                    raise TypeError('error')
                return val ** 2

            return Side.effect(plus_inner)

        def inner(o):
            return Side.pure(o).bind(plus).bind(lambda v: Side.pure(v + 1))

        eff = Side.pure(10).map(lambda v: v + 10).bind(inner).map(lambda v: v + 1)
        rp = run_rebuild(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 20)

        rp = run_rebuild(rp.remainder)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, None)

        rp = run_rebuild(rp.remainder)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 402)

        g = -2
        rp = insist(eff, attempts=5)
        self.assertEqual(rp.last_successfully, 402)

    def test_retry_nested_from_continuation(self):
        g = 0

        def plus(val):
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return val ** 2

        def inner(o):
            return Side.pure(o).map(plus).bind(lambda v: Side.effect(lambda: v + 1))

        eff = Side.pure(10).map(lambda v: v + 10).bind(inner).map(lambda v: v + 1)
        rp = run_rebuild(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 20)

        rp = run_rebuild(rp.remainder)
        self.assertFalse(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 20)

        rp = run_rebuild(rp.remainder)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(rp.last_successfully, 402)

        g = -2
        self.assertEqual(insist(eff, attempts=5).last_successfully, 402)

    def test_side_effect1(self):
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

        eff = Side.pure(10).bind(lambda v: Side.pure(v * 2).map(side_effect).map(raiser)).map(lambda v: v - 100)
        rp = insist(eff, 1)
        self.assertEqual(rp.last_successfully, 400)
        rp = insist(rp.remainder, 2)
        self.assertEqual(rp.last_successfully, 300)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(kit, ["side_effect"])

    def test_side_effect2(self):
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
            return Side.effect(lambda: val + 1).map(side_effect_level2).map(raiser_level2).map(lambda v: v)

        def level1(val):
            return (
                Side.effect(lambda: val + 1)
                .bind(level2)
                .map(side_effect_level1)
                .map(raiser_level1)
                .map(lambda v: v)
            )

        eff = Side.pure(0).bind(level1).map(side_effect_level0)
        rp = insist(eff, 3)
        self.assertEqual(rp.last_successfully, 5)
        rp = insist(rp.remainder, 10)
        self.assertEqual(rp.last_successfully, 36)
        self.assertEqual(kit, [2, 1, 0])

    def test_bad_side_effect(self):
        g = 0

        def effect():
            nonlocal g
            g += 1
            if g < 2:
                raise TypeError

        eff = Side.effect(effect).bind(lambda _: Side.effect(effect))
        rp = insist(eff, attempts=1)
        rp = insist(rp.remainder, attempts=1)
        self.assertTrue(rp.completed_successfully)
        self.assertEqual(g, 3)

    def test_transformer_result_pure_chains(self):
        eff = SideT.pure(0).map(lambda x: x + 1).map(lambda x: x + 1)
        self.assertEqual(run(eff).value, 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully.value, 2)

        eff = SideT.pure(0).map_result(lambda x: Ok(x + 1)).map(lambda x: x + 1)
        self.assertEqual(run(eff).value, 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully.value, 2)

    def test_transformer_result_bind_chains(self):
        eff = SideT.pure(0).map(lambda x: x + 1).bind(lambda x: SideT.wrap_result(Ok(x + 1)))
        self.assertEqual(run(eff).value, 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully.value, 2)

        eff = SideT.pure(0).map_result(lambda x: Ok(x + 1)).map(lambda x: x + 1)
        self.assertEqual(run(eff).value, 2)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully.value, 2)

    def test_transformer_result_inner_error(self):
        eff = SideT.error(0).map(lambda x: x + 1).map(lambda x: x + 1)
        self.assertTrue(run(eff).is_error)
        self.assertEqual(run(eff).error, 0)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_error)
        self.assertEqual(res.value.error, 0)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully.error, 0)

        eff = SideT.pure(0).map_result(lambda x: Err(x + 1)).map(lambda x: x + 1)
        self.assertTrue(run(eff).is_error)
        self.assertEqual(run(eff).error, 1)

        res = run_safe(eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_error)
        self.assertEqual(res.value.error, 1)

        report = run_rebuild(eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully.error, 1)

    def test_transformer_result_triple_nested_chain_errors(self):
        g = 0

        def raiser():
            nonlocal g
            g += 1
            if g < 3:
                raise TypeError('error')
            return Ok(None)

        def inner_second_chain(val: int):
            return SideT.effect(raiser).map(lambda _: val + 1)

        def inner_first_chain(val: int):
            return SideT.effect(lambda: Ok(val ** 2)).bind(inner_second_chain)

        eff = SideT.pure(5).map(lambda v: v + 5).bind(inner_first_chain)
        rp = run_rebuild(eff)
        self.assertFalse(rp.completed_successfully)
        self.assertTrue(rp.last_successfully.is_ok)
        self.assertEqual(rp.last_successfully.value, 100)
        self.assertIsInstance(rp.exception, TypeError)

        rp = insist(rp.remainder, 2)
        self.assertTrue(rp.completed_successfully)
        self.assertTrue(rp.last_successfully.is_ok)
        self.assertEqual(rp.last_successfully.get_or_else(0), 101)
        self.assertIs(rp.exception, None)

    def test_transformer_result_wrap_side(self):
        eff = Side.pure(0).map(lambda x: x + 1).bind(lambda x: Side.effect(lambda: x + 1))
        t_eff = SideT.wrap_side(eff)
        self.assertTrue(run(t_eff).is_ok)
        self.assertEqual(run(t_eff).value, 2)

        res = run_safe(t_eff)
        self.assertTrue(res.is_ok)
        self.assertTrue(res.value.is_ok)
        self.assertEqual(res.value.value, 2)

        report = run_rebuild(t_eff)
        self.assertTrue(report.completed_successfully)
        self.assertEqual(report.last_successfully.value, 2)


if __name__ == '__main__':
    unittest.main()

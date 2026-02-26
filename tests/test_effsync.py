import unittest

from mafunca.exceptions import MonadError
from mafunca.effsync import EffSync
from mafunca.triple import Right, Left, Nothing


class TestEffSync(unittest.TestCase):

    def test_effect_monad(self):
        eff = EffSync.of(0).map(lambda x: x + 1).bind(lambda x: EffSync(lambda: x + 1))
        self.assertEqual(eff.run(), 2)

        eff = EffSync(lambda: 0).map(lambda x: x + 1).bind(lambda x: EffSync(lambda: x + 1))
        self.assertEqual(eff.run(), 2)

        # working with a good Triple entity
        eff = (
            EffSync.of(0)
            .map(lambda x: Right(x + 1))
            .bind(lambda tm: EffSync(lambda: tm.map(lambda x: x + 1)))
            .bind(lambda tm: EffSync(lambda: tm.map(lambda x: x + 10)))
        )
        self.assertEqual(eff.run().unfold(), 12)
        self.assertTrue(eff.run().is_right)

        # short circuit on bad Triple entities
        eff = (
            EffSync.of(0)
            .map(lambda _: Left('error'))
            .bind(lambda x: EffSync(lambda: x + 1))
            .bind(lambda x: EffSync(lambda: x + 1))
        )
        self.assertEqual(eff.run().unfold(left=lambda x: (x,)), ('error',))

        # short circuit on bad Triple entities
        eff = EffSync.of(0).map(lambda _: Nothing()).map(lambda x: x + 1)
        self.assertEqual(eff.run().get_or_else("There was a Nothing"), "There was a Nothing")
        self.assertTrue(eff.run().is_nothing)

    def test_catch_errors(self):
        def error_raiser():
            raise TypeError

        # catching errors
        eff = (
            EffSync.of(0)
            .map(error_raiser)
            .catch(lambda _: 1)
            .bind(lambda x: EffSync(lambda: x + 1))
            .map(error_raiser)
            .catch(lambda _: EffSync(lambda: -10))
            .bind(lambda x: EffSync(lambda: x + 9))
        )

        self.assertEqual(eff.run(), -1)

        # if there are no errors, the catch method has no effect
        eff = (
            EffSync.of(0)
            .map(lambda x: x + 5)
            .catch(lambda _: 0)     # no effect here
            .bind(lambda x: EffSync(lambda: x + 5))
            .map(lambda x: x + 5)
            .catch(lambda: EffSync(error_raiser))    # no effect here
            .bind(lambda x: EffSync(lambda: x + 5))
        )
        self.assertEqual(eff.run(), 20)

        eff = (
            EffSync(lambda: 0)
            .map(lambda _: error_raiser())
            .catch(lambda _: error_raiser())
            .catch(lambda _: 0)
            .map(lambda x: x + 1)
            .catch(lambda _: EffSync(lambda: -10))   # no effect here
            .bind(lambda x: EffSync(lambda: x + 1))
        )
        self.assertEqual(eff.run(), 2)

        # short circuit on bad Triple entities in catch method
        eff = (
            EffSync.of(0)
            .map(lambda _: error_raiser())
            .catch(lambda _: Nothing())
            .map(lambda x: x + 1)
            .bind(lambda x: EffSync(lambda: x + 1))
        )
        self.assertTrue(eff.run().is_nothing)

    def test_ensure(self):
        def error_raiser():
            raise TypeError

        g = 0

        def side_effect():
            nonlocal g
            g += 10

        with self.assertRaises(TypeError):
            EffSync(lambda: 0).map(lambda _: error_raiser()).ensure(lambda: side_effect()).run()
        self.assertEqual(g, 10)

        eff = EffSync(lambda: 0).map(lambda x: x + 1).ensure(lambda: side_effect()).map(lambda x: x + 1)
        self.assertEqual(eff.run(), 2)
        self.assertEqual(g, 20)

    def test_contract_violation(self):
        async def violated():
            return 1

        with self.assertRaises(MonadError):
            EffSync(violated)

        with self.assertRaises(MonadError):
            EffSync(lambda: 10).map(lambda x: EffSync.of(x)).run()

        with self.assertRaises(MonadError):
            EffSync(lambda: 10).bind(lambda x: x + 1).run()


if __name__ == '__main__':
    unittest.main()

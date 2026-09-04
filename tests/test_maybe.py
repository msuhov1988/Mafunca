import unittest

from mafunca.maybe import Just, Nothing, just, nothing, is_just, is_nothing, from_null
from mafunca.maybe_direct import fmap, bind, fold, get_or_else, ap
from mafunca.maybe_lift import lift, lift2, lift3, lift4

from mafunca.flow import flow
import mafunca.maybe_flow as mf


class TestMaybe(unittest.TestCase):
    def test_introspection(self):
        right = just(1)
        self.assertTrue(is_just(right))
        self.assertFalse(is_nothing(right))        

        err = nothing()
        self.assertFalse(is_just(err))
        self.assertTrue(is_nothing(err))

    def test_just_chains(self):        
        res1 = just(2)
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: just(x + 1))
        res1 = fold(res1, on_just=lambda x: x ** 2, on_nothing=lambda: 0)       
        self.assertEqual(res1, 16)

        res2 = flow(
            just(2),
            mf.fmap(lambda x: x + 1),
            mf.bind(lambda x: just(x + 1)),
            mf.fold(on_just=lambda x: x ** 2, on_nothing=lambda: 0)
        )
        self.assertEqual(res2, 16)
        
        res3 = just(1)
        res3 = fmap(res3, lambda x: x + 1)
        res3 = bind(res3, lambda x: just(x + 1))
        res3 = get_or_else(res3, 100)
        self.assertEqual(res3, 3)

        res4 = flow(
            just(1),
            mf.fmap(lambda x: x + 1),
            mf.bind(lambda x: just(x + 1)),
            mf.get_or_else(100)
        )
        self.assertEqual(res4, 3)
        
        res5 = just(1)
        res5 = fmap(res5, lambda x: x + 1)
        res5 = fmap(res5, lambda x: just(x + 1))
        res5 = fold(res5, on_just=lambda v: v, on_nothing=lambda: just(0)) 
        self.assertIsInstance(res5, Just)
        self.assertEqual(get_or_else(res5, 100), 3)

        res6 = flow(
            just(1),
            mf.fmap(lambda x: x + 1),
            mf.fmap(lambda x: just(x + 1)),
            mf.fold(on_just=lambda v: v, on_nothing=lambda: just(0))
        )
        self.assertIsInstance(res6, Just)
        self.assertEqual(get_or_else(res6, 100), 3)
        
        res7 = just(2)
        res7 = bind(res7, lambda _: nothing())
        res7 = fmap(res7, lambda x: x + 1)
        self.assertIsInstance(res7, Nothing)
        res7 = fold(res7, on_just=lambda v: v, on_nothing=lambda: 0)
        self.assertTrue(res7 == 0)

        res8 = flow(
            just(2),
            mf.bind(lambda _: nothing()),
            mf.fmap(lambda x: x + 1)   
        )
        self.assertIsInstance(res8, Nothing)
        res8 = flow(res8, mf.fold(on_just=lambda v: v, on_nothing=lambda: 0))
        self.assertTrue(res8 == 0)

    def test_nothing_chains(self):        
        res1 = nothing()
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: just(x + 1))
        self.assertIsInstance(res1, Nothing)

        res2 = flow(nothing(), mf.fmap(lambda x: x + 1), mf.bind(lambda x: just(x + 1)))
        self.assertIsInstance(res2, Nothing)
        
        res3 = nothing()
        res3 = fmap(res3, lambda x: x + 1)
        res3 = bind(res3, lambda x: just(x + 1))
        self.assertIsInstance(res3, Nothing)
        res3 = get_or_else(res3, 100)        
        self.assertEqual(res3, 100)

        res4 = flow(nothing(), mf.fmap(lambda x: x + 1), mf.bind(lambda x: just(x + 1)))
        self.assertIsInstance(res4, Nothing)
        res4 = flow(res4, mf.get_or_else(100))
        self.assertEqual(res4, 100)

    def test_nullable(self):        
        res1 = from_null(1)
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: just(x))
        self.assertTrue(is_just(res1))
        self.assertEqual(get_or_else(res1, 100), 2)

        res2 = flow(
            from_null(1),
            mf.fmap(lambda x: x + 1),
            mf.bind(lambda x: just(x)),
            mf.get_or_else(100)
        )
        self.assertEqual(res2, 2)
        
        res3 = from_null(None)
        res3 = fmap(res3, lambda _: 0)
        res3 = bind(res3, lambda x: just(x))
        self.assertTrue(is_nothing(res3))
        self.assertEqual(get_or_else(res3, 100), 100)    

        res4 = flow(
            from_null(None),
            mf.fmap(lambda _: 0),
            mf.bind(lambda x: just(x)),
            mf.get_or_else(100)    
        )
        self.assertEqual(res4, 100)  
        
        res5 = from_null(4, is_nullable=lambda num: num % 2 == 0)
        res5 = fmap(res5, lambda x: x + 1)
        res5 = bind(res5, lambda x: just(x))
        self.assertTrue(is_nothing(res5))
        self.assertEqual(get_or_else(res5, 100), 100)

        res6 = flow(
            from_null(4, is_nullable=lambda num: num % 2 == 0),
            mf.fmap(lambda x: x + 1),
            mf.bind(lambda x: just(x)),
            mf.get_or_else(100),  
        )
        self.assertEqual(res6, 100)

    def test_nullable_yield(self):
        res = (from_null(i, lambda v: v % 2 == 0) for i in range(10))
        res = list((m for m in res if is_nothing(m)))
        self.assertEqual(len(res), 5)

    def test_ap(self):
        def one(a: int):
            return [a]
        
        res = get_or_else(ap(just(10), just(one)), [0])
        self.assertEqual(res, [10])
        
        res = ap(nothing(), just(one))
        self.assertTrue(is_nothing(res))
        self.assertEqual(get_or_else(res, 0), 0)   

    def test_ap_flow(self):
            def one(a: int):
    
                def one_inner(b: int):
    
                    def one_inner_inner(c: int):
                        return [a, b, c]
    
                    return one_inner_inner
    
                return one_inner
    
            res = flow(just(one), mf.ap(just(1)), mf.ap(just(2)), mf.ap(just(3)))
            res = get_or_else(res, [])
            self.assertEqual(res, [1, 2, 3])
    
            res = flow(just(one), mf.ap(just(1)), mf.ap(just(2)), mf.ap(nothing()))
            res = get_or_else(res, [])
            self.assertEqual(res, []) 
          
    def test_lift2(self):
        def two(a: int, b: int):
             return [a, b]
        
        res = get_or_else(lift2(two, just(1), just(2)), [])
        self.assertEqual(res, [1, 2])
        res = lift2(two, just(1), nothing())
        self.assertTrue(is_nothing(res))
        self.assertEqual(get_or_else(res, 100), 100)
        res = get_or_else(lift2(two, nothing(), just(2)), [])
        self.assertEqual(res, [])

    def test_lift3(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]
        
        res = get_or_else(lift3(three, just(1), just(2), just(3)), [0])
        self.assertEqual(res, [1, 2, 3])
        res = lift3(three, just(1), just(2), nothing())
        self.assertTrue(is_nothing(res))
        self.assertEqual(get_or_else(res, 100), 100)
        res = get_or_else(lift3(three, just(1), nothing(), just(3)), [])
        self.assertEqual(res, [])

    def test_lift4(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]
        
        res = get_or_else(lift4(four, just(1), just(2), just(3), just(4)), [])
        self.assertEqual(res, [1, 2, 3, 4])
        res = lift4(four, just(1), nothing(), just(3), just(4))
        self.assertTrue(is_nothing(res))        
        res = get_or_else(lift4(four, just(1), nothing(), just(3), just(4)), [])
        self.assertEqual(res, [])

    def test_lift(self):
        def many(a: int, b: int, c: int, d: int, e: int):
            return [a, b, c, d, e]
        
        res = lift(many, just(1), just(2), just(3), just(4), just(5))
        res = fold(res, on_just=lambda v: v, on_nothing=lambda : [])
        self.assertEqual(res, [1, 2, 3, 4, 5])
        res = lift(many, just(1), nothing(), just(3), just(4), just(5))
        self.assertTrue(is_nothing(res))        
        res = get_or_else(lift(many, just(1), nothing(), just(3), just(4), just(5)), [])
        self.assertEqual(res, []) 


if __name__ == "__main__":
    unittest.main()

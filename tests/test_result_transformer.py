import unittest

from mafunca.result import success as result_success, fail as result_fail
from mafunca.maybe import Just, Nothing, nothing as maybe_empty
from mafunca.maybe_direct import fmap as maybe_map
from mafunca.trans_result import success, nothing, fail, lift_maybe, lift_result
from mafunca.trans_result import is_success, is_nothing, is_fail, from_null, from_try
from mafunca.trans_result_direct import fmap, fmap_error, fmap_maybe, fmap_result, bind, fold, get_or_else, ap
from mafunca.trans_result_lift import lift2, lift3, lift4, lift
import mafunca.trans_result_flow as rf
from mafunca.flow import flow

from mafunca.common.exceptions import MonadError


class TestResultMaybeT(unittest.TestCase):
    def test_introspection_forward(self):
        res = success(3)
        self.assertTrue(is_success(res))
        self.assertFalse(is_fail(res))
        self.assertFalse(is_nothing(res))        

        res = nothing()
        self.assertFalse(is_success(res))
        self.assertFalse(is_fail(res))
        self.assertTrue(is_nothing(res)) 

        res = fail(None)
        self.assertFalse(is_success(res))
        self.assertTrue(is_fail(res))
        self.assertFalse(is_nothing(res)) 

        res = lift_maybe(Just(3))
        self.assertTrue(is_success(res))
        self.assertFalse(is_fail(res))
        self.assertFalse(is_nothing(res))

        res = lift_maybe(maybe_empty())
        self.assertFalse(is_success(res))
        self.assertFalse(is_fail(res))
        self.assertTrue(is_nothing(res))

        res = lift_result(result_success(3))
        self.assertTrue(is_success(res))
        self.assertFalse(is_fail(res))
        self.assertFalse(is_nothing(res))
        
        res = lift_result(result_fail(None))
        self.assertFalse(is_success(res))
        self.assertTrue(is_fail(res))
        self.assertFalse(is_nothing(res))
    
    def test_map_bind(self):        
        res1 = success(0)
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: success(x + 1))
        res1 = fmap(res1, lambda x: x + 1)
        self.assertEqual(get_or_else(res1, 100), 3)
        res1 = fold(res1, on_success=lambda m: maybe_map(m, lambda x: x ** 2), on_fail=lambda _: 0)
        self.assertEqual(res1, Just(9))
        
        res2 = flow(
            success(0),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda _: nothing()),
            rf.fmap(lambda x: x + 1),
        )
        self.assertTrue(is_nothing(res2))
        self.assertEqual(flow(res2, rf.get_or_else(100)), 100)
        res2 = flow(res2, rf.fold(on_success=lambda m: maybe_map(m, lambda x: x ** 2), on_fail=lambda _: 0))
        self.assertIsInstance(res2, Nothing)
        
        res3 = flow(
            nothing(),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: success(x + 1)),  
            rf.fmap(lambda x: x + 1),
            rf.get_or_else(100)  
        )        
        self.assertEqual(res3, 100)       
        
        res4 = flow(
            success(0),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: fail(x + 1)),  
            rf.fmap(lambda x: x + 1),            
        )                
        self.assertTrue(is_fail(res4))
        self.assertEqual(get_or_else(res4, 100), 100)
        self.assertEqual(flow(res4, rf.fold(on_success=lambda m: maybe_map(m, lambda x: x ** 2), on_fail=lambda e: e)), 2)      
        
        res5 = fail(0)
        res5 = bind(res5, lambda x: success(x + 1))
        res5 = bind(res5, lambda x: fail(x + 1))
        self.assertTrue(is_fail(res5))        
        self.assertEqual(get_or_else(res5, 100), 100)
        res5 = fold(res5, on_success=lambda m: maybe_map(m, lambda x: x ** 2), on_fail=lambda e: e)
        self.assertEqual(res5, 0)

    def test_map_maybe_and_result(self):        
        res1 = flow(
            success(0),
            rf.fmap_maybe(lambda x: Just(x + 1)),
            rf.bind(lambda x: success(x + 1)),            
        )
        self.assertEqual(get_or_else(res1, 100), 2)
        res1 = fold(res1, on_success=lambda m: maybe_map(m, lambda x: x ** 2), on_fail=lambda _: Just(0))
        self.assertEqual(res1, Just(4))
        
        res2 = success(0)
        res2 = fmap_maybe(res2, lambda _: maybe_empty())
        res2 = fmap(res2, lambda x: x + 1)       
        self.assertTrue(is_nothing(res2))
        self.assertEqual(get_or_else(res2, 100), 100)
        res2 = flow(res2, rf.fold(on_success=lambda m: maybe_map(m, lambda x: x ** 2), on_fail=lambda _: Just(0)))
        self.assertIsInstance(res2, Nothing)
        
        res3 = flow(
            success(0),
            rf.fmap_result(lambda x: result_success(x + 1)),
            rf.bind(lambda x: success(x + 1)),
        )

        self.assertEqual(flow(res3, rf.get_or_else(100)), 2)
        res3 = flow(res3, rf.fold(on_success=lambda m: maybe_map(m, lambda x: x ** 2), on_fail=lambda _: Just(0)))
        self.assertEqual(res3, Just(4))
        
        res4 = success(0)
        res4 = fmap_result(res4, lambda x: fail(x + 1))
        res4 = fmap(res4, lambda x: x)
        self.assertTrue(is_fail(res4))        
        self.assertEqual(get_or_else(res4, 100), 100)
        res4 = fold(res4, on_success=lambda m: maybe_map(m, lambda _: 100), on_fail=lambda _: Just(0))
        self.assertEqual(res4, Just(0))

    def test_map_error(self):        
        res1 = flow(
            success(0),
            rf.fmap_error(lambda e: e + 1),
            rf.bind(lambda x: success(x + 10))
        )
        self.assertEqual(flow(res1, rf.get_or_else(100)), 10)
        res1 = flow(res1, rf.fold(on_success=lambda m: m, on_fail=lambda _: Just(0)))
        self.assertEqual(res1, Just(10))
        
        res2 = fail(0)
        res2 = bind(res2, lambda x: success(x + 10))
        res2 = fmap_error(res2, lambda e: e + 1)
        self.assertTrue(is_fail(res2))        
        res2 = fold(res2, on_success=lambda m: m, on_fail=lambda e: Just(e))
        self.assertEqual(res2, Just(1))
        
        res3 = flow(
            success(0),
            rf.bind(lambda x: fail(x + 1)),
            rf.fmap_error(lambda e: e + 1),
        )
        self.assertTrue(is_fail(res3))        
        res3 = flow(res3, rf.fold(on_success=lambda m: m, on_fail=lambda e: Just(e)))
        self.assertEqual(res3, Just(2))
        
        res4 = success(0)
        res4 = fmap_result(res4, lambda x: result_fail(x + 1))
        res4 = fmap_error(res4, lambda e: e + 1)
        self.assertTrue(is_fail(res4))        
        res4 = fold(res4, on_success=lambda m: m, on_fail=lambda e: Just(e))
        self.assertEqual(res4, Just(2))
        
        res5 = flow(
            success(0),
            rf.fmap_maybe(lambda _: maybe_empty()),
            rf.fmap_error(lambda e: e + 1),
        )
        self.assertTrue(is_nothing(res5))
        self.assertEqual(flow(res5, rf.get_or_else(100)), 100)
        res5 = flow(res5, rf.fold(on_success=lambda _: 100, on_fail=lambda _: 0))
        self.assertEqual(res5, 100)

    def test_from_null(self):
        res1 = from_null(1)
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: success(x + 1))
        self.assertTrue(is_success(res1))
        self.assertEqual(get_or_else(res1, 100), 3)
        
        res2 = flow(
            from_null(None),
            rf.fmap(lambda x: x),
            rf.bind(lambda x: success(x)),
        )
        self.assertTrue(is_nothing(res2))
        self.assertEqual(get_or_else(res2, 100), 100)
        
        res3 = from_null(4, is_nullable=lambda num: num % 2 == 0)
        res3 = bind(res3, lambda x: success(x + 1))
        self.assertTrue(is_nothing(res3))
        self.assertEqual(get_or_else(res3, 100), 100)

    def test_from_try_errors(self):         
        @from_try
        def test(a: int):
            if a == 0:
                raise TypeError('error')
            return a       
        
        res1 = test(0)
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: success(x + 1))
        self.assertTrue(is_fail(res1))
        self.assertTrue(fold(res1, on_success=lambda _: False, on_fail=lambda e: isinstance(e, TypeError)))       
        
        res2 = flow(
            test(10),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: success(x + 1)),
        )
        self.assertTrue(is_success(res2))
        self.assertEqual(get_or_else(res2, 0), 12)     
   
    def test_from_try_monad_error(self):
        @from_try
        def raiser(a: int):
            _ = a + 1
            raise MonadError("test", "test", "test")

        with self.assertRaises(MonadError):
            raiser(1)

    def test_ap(self):
        def one(a: int):
            return [a]
        
        res1 = get_or_else(ap(success(10), success(one)), [0])
        self.assertEqual(res1, [10])

        res2 = ap(fail(10), success(one))
        self.assertTrue(is_fail(res2))
        self.assertEqual(get_or_else(res2, 0), 0)

        res3 = flow(success(one), rf.ap(fail(10)))
        self.assertTrue(is_fail(res3))
        self.assertEqual(get_or_else(res3, 0), 0)       
       
        res4 = ap(nothing(), success(one))
        self.assertTrue(is_nothing(res4))
        self.assertEqual(get_or_else(res4, 0), 0)

        res5 = flow(success(one), rf.ap(nothing()))
        self.assertTrue(is_nothing(res5))
        self.assertEqual(get_or_else(res5, 0), 0) 

    def test_lift2(self):
        def two(a: int, b: int):
            return [a, b]

        res = lift2(two, success(1), success(2))        
        self.assertEqual(get_or_else(res, []), [1, 2])
        res = lift2(two, success(1), fail(2))
        self.assertTrue(is_fail(res))        
        res = lift2(two, success(1), nothing())
        self.assertTrue(is_nothing(res))

    def test_lift3(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        res = lift3(three, success(1), success(2), success(3))
        self.assertEqual(get_or_else(res, []), [1, 2, 3])

        res = lift3(three, success(1), fail(2), success(3))
        self.assertTrue(is_fail(res))        

        res = lift3(three, success(1), nothing(), success(3))
        self.assertTrue(is_nothing(res))

        res = lift3(three, nothing(), fail(2), success(3))
        self.assertTrue(is_nothing(res))

        res = lift3(three, success(3), fail(2), nothing())
        self.assertTrue(is_fail(res)) 

    def test_lift4(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]        

        res = lift4(four, success(1), success(2), success(3), success(4))
        self.assertEqual(get_or_else(res, []), [1, 2, 3, 4])

        res = lift4(four, success(1), fail(2), fail(3), success(4))
        self.assertTrue(is_fail(res))
        error = res.error if is_fail(res) else 0
        self.assertEqual(error, 2)

        res = lift4(four, success(1), nothing(), success(3), success(4))
        self.assertTrue(is_nothing(res))

        res = lift4(four, nothing(), fail(2), success(3), success(4))
        self.assertTrue(is_nothing(res))

        res = lift4(four, success(3), fail(2), nothing(), success(4))
        self.assertTrue(is_fail(res))        

    def test_lift(self):
        def many(a: int, b: int, c: int, d: int, e: int):
            return [a, b, c, d, e]       
        
        res = lift(many, success(1), success(2), success(3), success(4), success(5))        
        self.assertEqual(get_or_else(res, []), [1, 2, 3, 4, 5])

        res = lift(many, success(1), fail(2), success(3), success(4), success(5))
        self.assertTrue(is_fail(res))
        error = res.error if is_fail(res) else 0
        self.assertEqual(error, 2)

        res = lift(many, success(1), nothing(), success(3), success(4), success(5))
        self.assertTrue(is_nothing(res))

        res = lift(many, success(1), fail(2), nothing(), success(4), success(5))
        self.assertTrue(is_fail(res))        

        res = lift(many, success(1), nothing(), fail(3), success(4), success(5))
        self.assertTrue(is_nothing(res))


if __name__ == "__main__":
    unittest.main()

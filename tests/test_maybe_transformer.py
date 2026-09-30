import unittest
from typing import Never

from mafunca.result.build import Success, Fail, Result, success as result_success, fail as result_fail
from mafunca.maybe.build import Just, Nothing, just as maybe_just, nothing as maybe_nothing
from mafunca.result.direct import fmap as result_map
from mafunca.maybe_trans.build import just, nothing, fail, lift_maybe, lift_result, Step, do, Do
from mafunca.maybe_trans.build import is_just, is_nothing, is_fail, from_null, from_try
from mafunca.maybe_trans.direct import fmap, fmap_error, fmap_maybe, fmap_result, bind, fold, get_or_else, ap
from mafunca.maybe_trans.lift import lift2, lift3, lift4, lift
import mafunca.maybe_trans.flow as rf
from mafunca.flow import flow

from mafunca.common.exceptions import MonadError


class TestMaybeResultT(unittest.TestCase):
    def test_introspection_forward(self):
        res = just(3)
        self.assertTrue(is_just(res))
        self.assertFalse(is_fail(res))
        self.assertFalse(is_nothing(res))        

        res = nothing()
        self.assertFalse(is_just(res))
        self.assertFalse(is_fail(res))
        self.assertTrue(is_nothing(res)) 

        res = fail(None)
        self.assertFalse(is_just(res))
        self.assertTrue(is_fail(res))
        self.assertFalse(is_nothing(res)) 

        res = lift_maybe(maybe_just(3))
        self.assertTrue(is_just(res))
        self.assertFalse(is_fail(res))
        self.assertFalse(is_nothing(res))

        res = lift_maybe(maybe_nothing())
        self.assertFalse(is_just(res))
        self.assertFalse(is_fail(res))
        self.assertTrue(is_nothing(res))

        res = lift_result(result_success(3))
        self.assertTrue(is_just(res))
        self.assertFalse(is_fail(res))
        self.assertFalse(is_nothing(res))
        
        res = lift_result(result_fail(None))
        self.assertFalse(is_just(res))
        self.assertTrue(is_fail(res))
        self.assertFalse(is_nothing(res))
    
    def test_map_bind(self):        
        res1 = just(0)
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: just(x + 1))
        res1 = fmap(res1, lambda x: x + 1)
        self.assertEqual(get_or_else(res1, 100), 3)
        res1 = fold(res1, on_just=lambda m: result_map(m, lambda x: x ** 2), on_nothing=lambda: result_success(0))
        self.assertEqual(res1, Success(9))
        
        res2 = flow(
            just(0),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda _: nothing()),
            rf.fmap(lambda x: x + 1),
        )
        self.assertTrue(is_nothing(res2))
        self.assertEqual(flow(res2, rf.get_or_else(100)), 100)
        res2 = flow(res2, rf.fold(on_just=lambda m: result_map(m, lambda x: x ** 2), on_nothing=lambda : result_success(0)))
        self.assertEqual(res2, Success(0))
        
        res3 = flow(
            nothing(),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: just(x + 1)),  
            rf.fmap(lambda x: x + 1),
            rf.get_or_else(100)  
        )        
        self.assertEqual(res3, 100)       
        
        res4 = flow(
            just(0),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: fail(x + 1)),  
            rf.fmap(lambda x: x + 1),            
        )                
        self.assertTrue(is_fail(res4))
        self.assertEqual(get_or_else(res4, 100), 100)
        self.assertEqual(flow(res4, rf.fold(on_just=lambda m: result_map(m, lambda x: x ** 2), on_nothing=lambda : result_fail(0))), Fail(2))      
        
        res5 = fail(0)
        res5 = bind(res5, lambda x: just(x + 1))
        res5 = bind(res5, lambda x: fail(x + 1))
        self.assertTrue(is_fail(res5))        
        self.assertEqual(get_or_else(res5, 100), 100)
        res5 = fold(res5, on_just=lambda m: result_map(m, lambda x: x ** 2), on_nothing=lambda : result_success(0))
        self.assertEqual(res5, Fail(0))

    def test_map_maybe_and_result(self):        
        res1 = flow(
            just(0),
            rf.fmap_maybe(lambda x: Just(x + 1)),
            rf.bind(lambda x: just(x + 1)),            
        )
        self.assertEqual(get_or_else(res1, 100), 2)
        res1 = fold(res1, on_just=lambda m: result_map(m, lambda x: x ** 2), on_nothing=lambda : Success(0))
        self.assertEqual(res1, Success(4))
        
        res2 = just(0)
        res2 = fmap_maybe(res2, lambda _: maybe_nothing())
        res2 = fmap(res2, lambda x: x + 1)       
        self.assertTrue(is_nothing(res2))
        self.assertEqual(get_or_else(res2, 100), 100)
        res2 = flow(res2, rf.fold(on_just=lambda m: result_map(m, lambda x: x ** 2), on_nothing=lambda : Success(0)))
        self.assertEqual(res2, Success(0))
        
        res3 = flow(
            just(0),
            rf.fmap_result(lambda x: result_success(x + 1)),
            rf.bind(lambda x: just(x + 1)),
        )

        self.assertEqual(flow(res3, rf.get_or_else(100)), 2)
        res3 = flow(res3, rf.fold(on_just=lambda m: result_map(m, lambda x: x ** 2), on_nothing=lambda : Fail(0)))
        self.assertEqual(res3, Success(4))
        
        res4 = just(0)
        res4 = fmap_result(res4, lambda x: result_fail(x + 1))
        res4 = fmap(res4, lambda x: x)
        self.assertTrue(is_fail(res4))        
        self.assertEqual(get_or_else(res4, 100), 100)
        res4 = fold(res4, on_just=lambda m: result_map(m, lambda _: 100), on_nothing=lambda : Success(0))
        self.assertEqual(res4, Fail(1))

    def test_map_error(self):        
        res1 = flow(
            just(0),
            rf.fmap_error(lambda e: e + 1),
            rf.bind(lambda x: just(x + 10))
        )
        self.assertEqual(flow(res1, rf.get_or_else(100)), 10)
        res1 = flow(res1, rf.fold(on_just=lambda m: m, on_nothing=lambda : Fail(0)))
        self.assertEqual(res1, Success(10))
        
        res2 = fail(0)
        res2 = bind(res2, lambda x: just(x + 10))
        res2 = fmap_error(res2, lambda e: e + 1)
        self.assertTrue(is_fail(res2))        
        res2 = fold(res2, on_just=lambda m: m, on_nothing=lambda : Success(0))
        self.assertEqual(res2, Fail(1))
        
        res3 = flow(
            just(0),
            rf.bind(lambda x: fail(x + 1)),
            rf.fmap_error(lambda e: e + 1),
        )
        self.assertTrue(is_fail(res3))        
        res3 = flow(res3, rf.fold(on_just=lambda m: m, on_nothing=lambda : Success(0)))
        self.assertEqual(res3, Fail(2))
        
        res4 = just(0)
        res4 = fmap_result(res4, lambda x: result_fail(x + 1))
        res4 = fmap_error(res4, lambda e: e + 1)
        self.assertTrue(is_fail(res4))        
        res4 = fold(res4, on_just=lambda m: m, on_nothing=lambda : Success(0))
        self.assertEqual(res4, Fail(2))
        
        res5 = flow(
            just(0),
            rf.fmap_maybe(lambda _: maybe_nothing()),
            rf.fmap_error(lambda e: e + 1),
        )
        self.assertTrue(is_nothing(res5))
        self.assertEqual(flow(res5, rf.get_or_else(100)), 100)
        res5 = flow(res5, rf.fold(on_just=lambda _: 100, on_nothing=lambda : 0))
        self.assertEqual(res5, 0)

    def test_from_null(self):
        res1 = from_null(1)
        res1 = fmap(res1, lambda x: x + 1)
        res1 = bind(res1, lambda x: just(x + 1))
        self.assertTrue(is_just(res1))
        self.assertEqual(get_or_else(res1, 100), 3)
        
        res2 = flow(
            from_null(None),
            rf.fmap(lambda x: x),
            rf.bind(lambda x: just(x)),
        )
        self.assertTrue(is_nothing(res2))
        self.assertEqual(get_or_else(res2, 100), 100)
        
        res3 = from_null(4, is_nullable=lambda num: num % 2 == 0)
        res3 = bind(res3, lambda x: just(x + 1))
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
        res1 = bind(res1, lambda x: just(x + 1))
        self.assertTrue(is_fail(res1))
        self.assertTrue(fold(res1, on_just=lambda _: True, on_nothing=lambda : False))       
        
        res2 = flow(
            test(10),
            rf.fmap(lambda x: x + 1),
            rf.bind(lambda x: just(x + 1)),
        )
        self.assertTrue(is_just(res2))
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
        
        res1 = get_or_else(ap(just(10), just(one)), [0])
        self.assertEqual(res1, [10])

        res2 = ap(fail(10), just(one))
        self.assertTrue(is_fail(res2))
        self.assertEqual(get_or_else(res2, 0), 0)
        
        res3 = flow(just(one), rf.ap(fail(10)))
        self.assertTrue(is_fail(res3))
        self.assertEqual(get_or_else(res3, 0), 0)       
       
        res4 = ap(nothing(), just(one))
        self.assertTrue(is_nothing(res4))
        self.assertEqual(get_or_else(res4, 0), 0)

        res5 = flow(just(one), rf.ap(nothing()))
        self.assertTrue(is_nothing(res5))
        self.assertEqual(get_or_else(res5, 0), 0) 

    def test_lift2(self):
        def two(a: int, b: int):
            return [a, b]

        res = lift2(two, just(1), just(2))        
        self.assertEqual(get_or_else(res, []), [1, 2])
        res = lift2(two, just(1), fail(2))
        self.assertTrue(is_fail(res))        
        res = lift2(two, just(1), nothing())
        self.assertTrue(is_nothing(res))

    def test_lift3(self):
        def three(a: int, b: int, c: int):
            return [a, b, c]

        res = lift3(three, just(1), just(2), just(3))
        self.assertEqual(get_or_else(res, []), [1, 2, 3])

        res = lift3(three, just(1), fail(2), just(3))
        self.assertTrue(is_fail(res))        

        res = lift3(three, just(1), nothing(), just(3))
        self.assertTrue(is_nothing(res))

        res = lift3(three, nothing(), fail(2), just(3))
        self.assertTrue(is_nothing(res))

        res = lift3(three, just(3), fail(2), nothing())
        self.assertTrue(is_fail(res)) 

    def test_lift4(self):
        def four(a: int, b: int, c: int, d: int):
            return [a, b, c, d]        

        res = lift4(four, just(1), just(2), just(3), just(4))
        self.assertEqual(get_or_else(res, []), [1, 2, 3, 4])

        res = lift4(four, just(1), fail(2), fail(3), just(4))
        self.assertTrue(is_fail(res))
        error = res.value.error if is_fail(res) else 0
        self.assertEqual(error, 2)

        res = lift4(four, just(1), nothing(), just(3), just(4))
        self.assertTrue(is_nothing(res))

        res = lift4(four, nothing(), fail(2), just(3), just(4))
        self.assertTrue(is_nothing(res))

        res = lift4(four, just(3), fail(2), nothing(), just(4))
        self.assertTrue(is_fail(res))        

    def test_lift(self):
        def many(a: int, b: int, c: int, d: int, e: int):
            return [a, b, c, d, e]       
        
        res = lift(many, just(1), just(2), just(3), just(4), just(5))        
        self.assertEqual(get_or_else(res, []), [1, 2, 3, 4, 5])

        res = lift(many, just(1), fail(2), just(3), just(4), just(5))
        self.assertTrue(is_fail(res))
        error = res.value.error if is_fail(res) else 0
        self.assertEqual(error, 2)

        res = lift(many, just(1), nothing(), just(3), just(4), just(5))
        self.assertTrue(is_nothing(res))

        res = lift(many, just(1), fail(2), nothing(), just(4), just(5))
        self.assertTrue(is_fail(res))        

        res = lift(many, just(1), nothing(), fail(3), just(4), just(5))
        self.assertTrue(is_nothing(res))

    def test_gen_ok(self):
        @do
        def add(a: int) -> Do[int, Never]:
            num = yield from Step(just(1))
            return num + a  

        maybe = add(2)
        self.assertIsInstance(maybe, Just) 
        self.assertIsInstance(maybe.value if isinstance(maybe, Just) else None, Success) 
        res = maybe.value if isinstance(maybe, Just) else result_fail(0)
        value = res.value if isinstance(res, Success) else None
        self.assertEqual(value, 3)

    def test_gen_ok_wraps(self):
        @do
        def add(a: int) -> Do[Result[int, Never], Never]:
            num = yield from Step(just(1))
            return Success(num + a)
    
        mb = add(2)
        self.assertIsInstance(mb, Just) 
        res = mb.value if isinstance(mb, Just) else result_fail(0)
        inner = res.value if isinstance(res, Success) else None
        self.assertIsInstance(inner, Success)

    def test_gen_ok_no_yield(self):
        @do
        def add(a: int) -> Do[int, Never]:
            if a == 0:
                return a
            num = yield from Step(just(1))
            return num + a 

        mb = add(0)
        self.assertIsInstance(mb, Just) 
        res = mb.value if isinstance(mb, Just) else result_fail(100)
        self.assertEqual(res.value if isinstance(res, Success) else 100, 0) 

        mb = add(2)
        self.assertIsInstance(res, Success) 
        res = mb.value if isinstance(mb, Just) else result_fail(0)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value if isinstance(res, Success) else 0, 3) 

    def test_gen_err_fail(self):
        @do
        def add(a: int) -> Do[int, str]:
            if a < 0:
                num = yield from Step(fail("negative"))
            num = yield from Step(just(1))
            return num + a

        mb = add(-1)
        self.assertIsInstance(mb, Just)
        res = mb.value if isinstance(mb, Just) else result_success(0) 
        self.assertEqual(res.error if isinstance(res, Fail) else None, "negative")  

        mb = add(2)
        self.assertIsInstance(mb, Just) 
        res = mb.value if isinstance(mb, Just) else result_fail(0) 
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value if isinstance(res, Success) else 0, 3) 

    def test_gen_err_nothing(self):
        @do
        def add(a: int) -> Do[int, Never]:
            if a < 0:
                num = yield from Step(nothing())
            num = yield from Step(just(1))
            return num + a

        mb = add(-1)
        self.assertIsInstance(mb, Nothing)
        
        mb = add(2)
        self.assertIsInstance(mb, Just) 
        res = mb.value if isinstance(mb, Just) else result_fail(0)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value if isinstance(res, Success) else 0, 3) 

    def test_gen_err_fail_first(self):
        @do
        def add(a: int) -> Do[int, int]:
            num1 = yield from Step(fail(1))
            num2 = yield from Step(fail(2))
            return num1 + num2 + a
    
        mb = add(3)
        self.assertIsInstance(mb, Just)
        res = mb.value if isinstance(mb, Just) else result_success(0)  
        self.assertEqual(res.error if isinstance(res, Fail) else None, 1) 

    def test_gen_err_wrapped_fail(self):
        @do
        def add(a: int) -> Do[int, Result[Never, int]]:
            num1 = yield from Step(fail(Fail(1)))           
            return num1 + a
        
        mb = add(3)
        self.assertIsInstance(mb, Just)
        res = mb.value if isinstance(mb, Just) else result_success(0)  
        self.assertIsInstance(res.error if isinstance(res, Fail) else None, Fail) 
        unwrapped_one = res.error if isinstance(res, Fail) else None         
        self.assertEqual(unwrapped_one.error if isinstance(unwrapped_one, Fail) else None, 1)

    def test_gen_err_raise_stop_iteration(self):
        @do
        def add(a: int) -> Do[int, Never]:
            if a < 0:
                raise StopIteration(a)
            num = yield from Step(just(1))
            return num + a

        with self.assertRaises(RuntimeError):
            _ = add(-10)

    def test_gen_chained_fail(self):
        @do
        def add(a: int) -> Do[int, str]:
            if a < 0:
                return (yield from Step(fail("negative")))
            num = yield from Step(just(1))
            return a + num

        @do
        def mul(m: int) -> Do[int, str]:
            a = yield from Step(add(m))
            return a * 2

        mb = mul(-1)
        self.assertIsInstance(mb, Just) 
        res = mb.value if isinstance(mb, Just) else result_success(0)
        self.assertIsInstance(res, Fail) 
        self.assertEqual(res.error if isinstance(res, Fail) else None, "negative") 

        mb = mul(2)
        self.assertIsInstance(mb, Just) 
        res = mb.value if isinstance(mb, Just) else result_fail(0)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value if isinstance(res, Success) else 0, 6)

    def test_gen_chained_nothing(self):
        @do
        def add(a: int) -> Do[int, Never]:
            if a < 0:
                return (yield from Step(nothing()))
            num = yield from Step(just(1))
            return a + num

        @do
        def mul(m: int) -> Do[int, Never]:
            a = yield from Step(add(m))
            return a * 2

        mb = mul(-1)
        self.assertIsInstance(mb, Nothing)         

        mb = mul(2)
        self.assertIsInstance(mb, Just) 
        res = mb.value if isinstance(mb, Just) else result_fail(0)
        self.assertIsInstance(res, Success)
        self.assertEqual(res.value if isinstance(res, Success) else 0, 6)


if __name__ == "__main__":
    unittest.main()

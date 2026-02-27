# Some useful things from the world of functional programming for python

### The goal is to provide them in the most practical form (at least from the author's perspective).
### The library is minimalistic and has no dependencies.


### [Simple monads on value](#simple-monads-on-value)
- [Description](#description)
- [Method table](#method-table)
- [Examples](#examples)
- [Additional functions](#additional-functions)

### [Effects](#effects)
- [Description of effects](#description-of-effects)
- [Effect methods](#effect-methods)
- [Effect examples](#effect-examples)

### [Currying](#currying)
- [Description of currying](#description-of-currying)
- [Currying examples](#currying-examples)

## Simple monads on value
### Description
These are well-known monads such as **Maybe**, **Either** or **Optional**, **Result**.  
One monad is implemented here, which **contains three states at once**:

- **Right**   - contains a successful result inside
- **Left**    - contains some kind of erroneous result inside 
- **Nothing** - an empty space that does not contain any data

They are all descendants of the abstract class **Triple** and have identical interfaces, including method signatures.  
**FEATURE**: you can use all three possible states in a single function chain without having to resort to any tricks like transformers and etc.  
**IMPORTANT**: Since this is a monad over a value (already available!) - only synchronous functions are allowed. Consider lazy monads for asynchronous functions.

```python
from mafunca.triple import Right, Left, Nothing
```

### Method table:
#### ++ - a passed function can return both - Triple monads and other values
  | Method                               | Description                                                                                | Right                                                                              | Left                                          | Nothing                                       |
  |--------------------------------------|--------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|-----------------------------------------------|-----------------------------------------------|
  | **.is_right**                        | Property - boolean flag                                                                    | `True`                                                                             | `False`                                       | `False`                                       |
  | **.is_nothing**                      | Property - boolean flag                                                                    | `False`                                                                            | `False`                                       | `True`                                        |
  | **.map(fn)**                         | fn - function that returns a NON-Triple value                                              | applies, wraps the result                                                          | returns itself                                | returns itself                                |
  | **.bind(fn)**                        | fn - function that returns a Triple value                                                  | applies                                                                            | returns itself                                | returns itself                                |
  | **.recover_from_left(fn) ++**        | fn - function for recover from error                                                       | returns itself                                                                     | applies, wraps non-Triple result in the Right | returns itself                                |
  | **.recover_from_nothing(fn) ++**     | fn - function without params for recover from emptiness                                    | returns itself                                                                     | returns itself                                | applies, wraps non-Triple result in the Right |
  | **.unfold(*, right, left, nothing)** | Applies a function without wrapping the result. As a rule, it completes the chain.         | applies 'right' function                                                           | applies 'left' function                       | applies 'nothing' function                    |
  | **.get_or_else(value)**              | Returns an internal or passed value                                                        | returns internal                                                                   | returns passed                                | returns passed                                |
  | **.ap(wrapped_val)**                 | wrapped_val - value enclosed in a Triple. Itself must be Right[function] or Left, Nothing. | applies wrapped_val to the internal function. Wraps non-Triple result in the Right | returns itself                                | returns itself                                |

### Examples
#### A "philosophical" example:
Let's say you call three functions, passing the results sequentially:
```python
result1 = f1(init_val)
result2 = f2(result1)
total = f3(result2)
```
But what if each of these functions can throw an exception or return **None**?  
How can we combine them without confusing checks, external **try except** blocks, or repeated exception throws?  
We can extend the standard **try except** mechanism in each of the functions as follows:
```python
from mafunca.triple import Right, Left, Nothing

# inside a function
try:
    return Right(some_inner_operation(arg))
except YourException as exc:
    return Left(exc)   
```
Replace explicit **None** returns:
```python
# inside a function
return None       # it was
return Nothing()  # become
```
Or combine both approaches at once:
```python
from mafunca.triple import Right, Left, Nothing
from mafunca.triple import TUtils

# inside a function
try:
    return TUtils.from_nullable(some_inner_operation(arg))
except YourException as exc:
    return Left(exc)   
```
Now we can write the following chain:
```python
# each of the functions now returns a Triple, so I'm using the 'bind' method
monadic_total = (
  Right(init_val)
  .bind(f1)
  .bind(f2)
  .bind(f3)
)
total = monadic_total.unfold(
  right=function_handle,
  left=function_notify_and_log,
  nothing=function_inaction
)
```
Or using recovery methods:
```python
monadic_total = (
  Right(init_val)
  .bind(f1)
  .bind(f2)
  .bind(f3)
  .recover_from_left(error_handler)
  .recove_from_nothing(emptiness_handler)
)

# since I know that Left and Nothing are processed
# I can only leave the 'right' case here
# leaving the default handlers for 'left' and 'nothing'
total = monadic_total.unfold(right=function_handle)
```

#### A "humorous" example:
```python
# for some reason I only want to process integers, skipping everything else
def joke(incoming):
    if isinstance(incoming, int):
        return Right(incoming)
    return Nothing()

# lambda returns non-Triple value, so I'm using the 'map' method
# let's assume that 'send_data' is a function that sends data somewhere
joke(100).map(lambda v: v + 1).unfold(right=send_data)    # ok, 101 has been sent
joke("Abc").map(lambda v: v + 1).unfold(right=send_data)  # no data has been sent
```

#### An applicative example:
How can we apply a monadic "short circuit" to a function with multiple arguments?
```python
def summa(a: int, b: int, c: int) -> int:
    return a + b + c
```
I want to make this function able to apply values wrapped in **Triple** 
and still terminate in a "short-circuit" fashion if one of the arguments is **Left** or **Nothing**.  
Let's rewrite it in the 'curried' form:
```python
def summa(a: int):
    def summa_second(b: int):
        def summa_third(c: int):
            return a + b + c
        return summa_third  
    return summa_second   
```
To avoid doing this manually, the library provides a special module:
```python
from mafunca.curry import curry, async_curry  # async_curry - for async functions

@curry
def summa(a: int, b: int, c: int) -> int:
    return a + b + c
```

Now, by wrapping the function in the **Right** container, I can use the **ap** method:
```python
from mafunca.curry import curry
from mafunca.triple import Right, Left, Nothing

@curry
def summa(a: int, b: int, c: int) -> int:
    return a + b + c

# NOTE: after each 'ap' method, a partially applied function is added to the container
Right(summa).ap(Right(1)).ap(Right(2)).ap(Right(3))       # Right(6)

Right(summa).ap(Left("Error")).ap(Right(2)).ap(Right(3))  # Left("Error")
Right(summa).ap(Right(1)).ap(Right(2)).ap(Nothing())      # Nothing()
```
Again, there is a special function to avoid writing such chains manually:
```python
from mafunca.curry import curry
from mafunca.triple import Right, Left, Nothing, TUtils

@curry
def summa(a: int, b: int, c: int) -> int:
    return a + b + c

TUtils.lift(summa, Right(1), Right(2), Right(3))  # Right(6)
```
It is possible without currying at all:
```python
from mafunca.triple import Right, Left, Nothing, TUtils

@TUtils.closer
def summa(a: int, b: int, c: int) -> int:
    return a + b + c

summa(1, 2, 3)                         # 6
summa(Right(1), Right(2), 3)           # 6
summa(Left("err"), Right(2), Right(3)) # Left('err')
summa(Right(1), Nothing(), Right(3))   # Nothing()
```

### Additional functions
```python
from mafunca.triple import TUtils
from mafunca.triple import impure, is_impure

# if you want to dive even deeper into FP
# you can mark functions that have side effects
# and their execution in Triple monad methods will be prohibited
@impure
def some_side_effect(arg): ...

is_impure(some_side_effect)     # True
Right(1).map(some_side_effect)  # raise MonadError 

TUtils.unit(1)  # Right(1)

TUtils.from_nullable(None)                                      # Nothing
TUtils.from_nullable({"a": 1}, predicate=lambda d: d.get("a"))  # Right
TUtils.from_nullable({"a": 1}, predicate=lambda d: d.get("b"))  # Nothing
TUtils.from_nullable(None, predicate=lambda a: a is None)       # Right !!!

@TUtils.from_try
def raiser():
    raise TypeError("error")

raiser()                             # Left(TypeError)
TUtils.from_try(lambda a: a + 1)(0)  # Right(1)

TUtils.is_bad(Left("err"))  # True
TUtils.is_bad(Nothing())    # True
TUtils.is_bad(Right(1))     # False
TUtils.is_bad(10)           # False

TUtils.lift    # see previous chapter - an applicative example
TUtils.closer  # see previous chapter - an applicative example
```

## Effects
### Description of effects
These are well-known **LAZY** monads such as **IO**.  
It contains not a value, but a function of the form **Callable[[], R]**, which we will call an effect.  
Why laziness?  
It allows you to describe side effects within a regular function, keeping it 'pure':
```python
from mafunca.triple import impure
from mafunca.effsync import EffSync

@impure
def database_communication(number: int): ...

@impure
def smtp_communication(addresses): ...

# this function remains 'pure'
def ordinary_function(a: int) -> EffSync:
    result = a ** 2
    return (
      EffSync(lambda: result)
      .map(database_communication)
      .bind(lambda addr: EffSync(lambda: smtp_communication(addr)))
    )

eff = ordinary_function(10)
eff.run()  # performing side effects
```
This way, we separate the description of effects from their execution.  

Two monads are implemented here:
- **Eff**   - for asynchronous effects, but it can also work with synchronous functions
- **EffSync**    - strictly for synchronous effects 
- 
**FEATURE**: Effects work with "bad" instances of the 'Triple' monad using the short-circuit principle (see examples below)

```python
from mafunca.eff import Eff
from mafunca.effsync import EffSync
```

### Effect methods
#### REMINDER: EffSync only works with synchronous functions, and Eff can accept any
#### **++** - a passed function can return both - monads of the same type and other values
| Method                  | Description                                                                                                                    | Eff                                                                                                       | EffSync                            |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|------------------------------------|
| **.map(fn)**            | fn - a function that returns a NON-effect container (NON-Eff for Eff, NON-EffSync for EffSync)                                 | returns new Eff                                                                                           | returns new EffSync                |
| **.map_to_thread(fn)**  | the same as **map**, but function must be strictly sync and it is executed in a separate thread                                | returns new Eff                                                                                           | -                                  |
| **.bind(fn)**           | fn - a function that returns the same container type                                                                           | returns new Eff                                                                                           | returns new EffSync                |
| **.bind_to_thread(fn)** | the same as **bind**, but function INSIDE THE RETURNED CONTAINER must be strictly sync and it is executed in a separate thread | returns new Eff                                                                                           | -                                  |
| **.catch(fn) ++**       | Intercepts errors. **fn** - function of the form **Callable[[Exc], R]**, where **Exc** - subtype of **Exception**              | returns new Eff                                                                                           | returns new EffSync                |
| **.ensure(fn)**         | Acts like **finally**. **fn** - function without parameters and a return value (returns None)                                  | returns new Eff                                                                                           | returns new EffSync                |
| **.to_task()**          | Wraps the inner effect into a Task. Inner effect must be a coroutine function.                                                 | returns asyncio.Task                                                                                      | -                                  | 
| **.run()**              | Performs a chain of effects. This method is **async** in **Eff** and has an optional **delay** parameter.                      | returns the result of inner effect or throws a **TimeOutError** when the wait exceeds the specified delay | returns the result of inner effect |
| **.of(value)**          | Static method                                                                                                                  | returns Eff(lambda: value)                                                                                | returns EffSync(lambda: value)     |


### Effect examples
#### The examples are "toy-like", but they reflect the essence
```python
import asyncio

from mafunca.eff import Eff
from mafunca.effsync import EffSync
from mafunca.triple import Left

# short circuit on bad Triple entity
eff = (
  EffSync.of(0)
  .map(lambda _: Left('error'))
  .bind(lambda x: EffSync(lambda: x + 1))
  .bind(lambda x: EffSync(lambda: x + 1))
)
eff.run()  # Left(error)

async def raiser():
   raise TypeError("error")

async_eff = Eff(raiser).catch(lambda e: 10)
asyncio.run(async_eff.run())  # 10, async_eff.run - async method


async_eff = Eff(raiser).ensure(lambda: print("finally"))
asyncio.run(async_eff.run())  # the word will be printed despite the uncaught exception
```

## Currying
### Description of currying

### Currying examples
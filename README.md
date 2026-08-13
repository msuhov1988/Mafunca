[![PyPI version](https://img.shields.io/pypi/v/mafunca.svg)](https://pypi.org/project/mafunca/)
[![Python versions](https://img.shields.io/pypi/pyversions/mafunca.svg)](https://pypi.org/project/mafunca/)
[![License](https://img.shields.io/pypi/l/mafunca.svg)](https://pypi.org/project/mafunca/)
## For version <=0.5.3, see old_docs.md

### Mafunca is a small FP library with a practical focus.
### Rather than trying to implement every functional abstraction, it concentrates on a few useful ideas: 
- ### make failures explicit
- ### avoid scattering `None` checks across the codebase
- ### describe side effects lazily, so functions remain pure while programs are being composed
### Mafunca is dependency-free, stack-safe in its effect system, strict about contracts and
### deliberately keeps synchronous and asynchronous computations separate

### [Installiation](#installation)
- [Install mafunca](#install-mafunca)

### [Error handling and missing values](#error-handling-and-missing-values)
- [Description](#description)
- [Result methods](#result-methods)
- [Maybe methods](#maybe-methods)
- [ResultT methods](#resultt-methods)
- [MaybeT methods](#maybet-methods)
- [Examples](#examples)

### [Currying](#currying)
- [Description of currying](#description-of-currying)
- [Currying examples](#currying-examples)

### [Effects](#effects)
- [Description of effects](#description-of-effects)
- [Synchronous effects](#synchronous-effects)
- [Asynchronous effects](#asynchronous-effects)
- [Transformers](#transformers)
- [General remarks](#general-remarks)
- [Effect examples](#effect-examples)

### [Exceptions](#exceptions)
- [Description of exceptions](#description-of-exceptions)

## Installation
### Install mafunca
```
pip install mafunca
```
```
python -m pip install mafunca
```

## Error handling and missing values
### Description
Of course, we will talk about monads.
To begin with, a small example:

Let's say you call three functions, passing the results sequentially:
```python
result1 = f1(val)
result2 = f2(result1)
final = f3(result2)
```
But what if each of these functions can throw an exception or return **None**, or both?  
How can we combine them without additional checks, external **try except** blocks, or repeated exception throws? 

**Case of errors only**  
We can extend the standard try except mechanism in each of the functions as follows:
```python
from mafunca.result import Ok, Err, Result

# Result[T, E] is just a TypeAlias for Ok[T] | Err[E]
def f1(...) -> Result[T, Exception]:
    try:
        ...
        return Ok(result_value)
    except Exception as err:
        return Err(err)
```
Or
```python
from mafunca.result import from_try

@from_try
def f1(...):
    # the function body is unchanged
    ...
```

**Case of missing values**
```python
from mafunca.maybe import Just, Nothing, Maybe, from_null

# Maybe[T] is just a TypeAlias for Just[T] | Nothing
def f1(...) -> Maybe[T]:
    ... 
    # Replace explicit None returns
    return None       # it was
    return Nothing()  # become
    ...
    # Replace normal returns
    return result_value        # it was
    return Just(result_value)  # become
    ...
    # Or two in one
    return from_null(is_nullable=lambda v: v is None)(operation_that_returns(...))
```

**Case of both errors and missing values**  
You need to use a transformer that includes all three states(normal result, absense, error):
```python
from mafunca.result_transformer import ResultT
from mafunca.result_transformer import just_of, nothing_of, error_of

#  ResultT[T, E] - container for a composite value of the form Result[Maybe[T], E]
#  Note that ResultT is not a TypeAlias, but a class
def f1(...) -> ResultT[T, Exception]:
    try:
        ... 
        # Replace explicit None returns
        return None          # it was
        return nothing_of()  # become
        ...
        # Replace normal returns
        return result_value           # it was
        return just_of(result_value)  # become
    except Exception as err:
        return error_of(err)
```
Or
```python
from mafunca.result_transformer import from_try

@from_try(is_nullable=lambda v: v is None)
def f1(...):
    # the function body is unchanged
    ...    
```
**Now we can write the following chain**:
```python
# no additional checks
# no external try except blocks
# no repeated exception throws
final_in_container = f1(val).bind(f2).bind(f3)
# all errors and missing values will be processed linearly using binding methods
# Note that final_in_container is a value inside a monad, so it still needs to be extracted
# How to do it? - see the method tables below
```

### Result methods:
```python
import mafunca.result  # the corresponding module
```
```python
Result: TypeAlias = Ok[T] | Err[E]
```
  | Method(`self` is omitted for brevity)                                    | Ok returns                   | Err returns            | Description                                                         |          
  |--------------------------------------------------------------------------|------------------------------|------------------------|---------------------------------------------------------------------|
  | is_ok                                                                    | `True`                       | `False`                | Property - boolean flag                                             |
  | is_error                                                                 | `False`                      | `True`                 | Property - boolean flag                                             |
  | <nobr>map(fn: Callable[[T], R]</nobr>                                    | `Ok[R]`                      | `self`                 | applies the function, wraps the result                              |
  | <nobr>bind(fn: Callable[[T], Result[R, E]])</nobr>                       | <nobr> `Result[R, E]`</nobr> | `self`                 | applies the function and does not wraps the result                  |
  | <nobr>map_error(fn: Callable[[E], NewE])</nobr>                          | `self`                       | `Err[NewE]`            | mapping the error on a new one                                      |
  | get_or_else(alter: T)                                                    | extracts                     | returns an alternative | extracts the internal value or returns an alternative               |
  | unfold(<br/>*,<br/>ok: Callable[[T], R],<br/>err: Callable[[E], R]<br/>) | `R`                          | `R`                    | extracts the internal value using the corresponding branch function |
### Result additional module functions:
  | Function                                                                                     | returns                                            | Description                                                                             |       
  |----------------------------------------------------------------------------------------------|----------------------------------------------------|-----------------------------------------------------------------------------------------|
  | ok_of(value: T)                                                                              | `Ok[T]`                                            | Wraps the value in a container                                                          |
  | err_of(error: E)                                                                             | `Err[E]`                                           | Wraps the error in a container                                                          |
  | <nobr>from_try(fn: Callable[..., R])</nobr>                                                  | <nobr>`Callable[..., Result[R, Exception]]`</nobr> | Decorator. Wraps `fn`, catches possible errors - heirs of `Exception`.                  | 
  | <nobr>ap(fn: Result[Callable[[T], R], E], val: Result[T, E])</nobr>                          | <nobr>`Result[R, E]`</nobr>                        | Applies value enclosed in the Result to a function also in the Result                   |
  | lift2(<br/>fn: Callable[[A1, A2], R],<br/>arg1: Result[A1, E],<br/>arg2: Result[A2, E]<br/>) | <nobr>`Result[R, E]`</nobr>                        | Applies wrapped values to a two-argument function                                       |
  | lift3, lift4                                                                                 | <nobr>`Result[R, E]`</nobr>                        | Similarly to lift2, but for functions with 3 and 4 positional arguments, respectively   |
  | lift(fn: Callable[..., R], *args: Result[Any, E])                                            | <nobr>`Result[R, E]`</nobr>                        | Similarly to lift2, but for a function with an arbitrary number of positional arguments |
### Maybe methods:
```python
import mafunca.maybe  # the corresponding module
```
```python
Maybe: TypeAlias = Just[T] | Nothing
```
  | Method(`self` is omitted for brevity)                                         | Just returns             | Nothing returns        | Description                                                         |          
  |-------------------------------------------------------------------------------|--------------------------|------------------------|---------------------------------------------------------------------|
  | is_just                                                                       | `True`                   | `False`                | Property - boolean flag                                             |
  | is_nothing                                                                    | `False`                  | `True`                 | Property - boolean flag                                             |
  | <nobr>map(fn: Callable[[T], R]</nobr>                                         | `Just[R]`                | `self`                 | applies the function, wraps the result                              |
  | <nobr>bind(fn: Callable[[T], Maybe[R]])</nobr>                                | <nobr> `Maybe[R]`</nobr> | `self`                 | applies the function and does not wraps the result                  |  
  | get_or_else(alter: T)                                                         | extracts                 | returns an alternative | extracts the internal value or returns an alternative               |
  | unfold(<br/>*,<br/>just: Callable[[T], R],<br/>nothing: Callable[[], R]<br/>) | `R`                      | `R`                    | extracts the internal value using the corresponding branch function |
### Maybe additional module functions:
  | Function                                                                                 | returns                                | Description                                                                             |       
  |------------------------------------------------------------------------------------------|----------------------------------------|-----------------------------------------------------------------------------------------|
  | just_of(value: T)                                                                        | `Just[T]`                              | Wraps the value in a container                                                          |
  | nothing_of()                                                                             | `Nothing`                              | Creates Nothing entity                                                                  |
  | <nobr>from_null(is_nullable: Callable[[R], bool] = lambda v: v is None)(value: R)</nobr> | <nobr>`Callable[[R], Maybe[R]]`</nobr> | Returns Nothing or wraps the value in Just based on the `is_nullable` result            | 
  | <nobr>ap(fn: Maybe[Callable[[T], R]], val: Maybe[T])</nobr>                              | <nobr>`Maybe[R]`</nobr>                | Applies value enclosed in the Maybe to a function also in the Maybe                     |
  | lift2(<br/>fn: Callable[[A1, A2], R],<br/>arg1: Maybe[A1],<br/>arg2: Maybe[A2]<br/>)     | <nobr>`Maybe[R]`</nobr>                | Applies wrapped values to a two-argument function                                       |
  | lift3, lift4                                                                             | <nobr>`Maybe[R]`</nobr>                | Similarly to lift2, but for functions with 3 and 4 positional arguments, respectively   |
  | lift(fn: Callable[..., R], *args: Maybe[Any])                                            | <nobr>`Maybe[R]`</nobr>                | Similarly to lift2, but for a function with an arbitrary number of positional arguments |
### ResultT methods:
```python
import mafunca.result_transformer  # the corresponding module
```
```python
class ResultT(Generic[T, E]):    
    inner: Result[Maybe[T], E]
```
  | Method(`self` is omitted for brevity)                                           | returns                         | Description                                                         |          
  |---------------------------------------------------------------------------------|---------------------------------|---------------------------------------------------------------------|
  | is_just                                                                         | `bool`                          | Property - boolean flag                                             |
  | is_nothing                                                                      | `bool`                          | Property - boolean flag                                             |
  | is_error                                                                        | `bool`                          | Property - boolean flag                                             |
  | <nobr>map(fn: Callable[[T], R])</nobr>                                          | <nobr>`ResultT[R, E]`</nobr>    | applies the function, wraps the result                              |
  | <nobr>map_maybe(fn: Callable[[T], Maybe[R]])</nobr>                             | <nobr>`ResultT[R, E]`</nobr>    | applies the function, wraps the result                              |
  | <nobr>map_result(fn: Callable[[T], Result[R, E]])</nobr>                        | <nobr>`ResultT[R, E]`</nobr>    | applies the function, wraps the result                              |
  | <nobr>bind(fn: Callable[[T], ResultT[R, E]])</nobr>                             | <nobr>`ResultT[R, E]`</nobr>    | applies the function and does not wraps the result                  |
  | <nobr>map_error(fn: Callable[[E], NewE])</nobr>                                 | <nobr>`ResultT[T, NewE]`</nobr> | mapping the error on a new one                                      |
  | get_or_else(alter: T)                                                           | extracts or alternative         | extracts the internal value or returns an alternative               |
  | unfold(<br/>*,<br/>ok: Callable[[Maybe[T]], R],<br/>err: Callable[[E], R]<br/>) | `R`                             | extracts the internal value using the corresponding branch function |
### ResultT additional module functions:
  | Function                                                                                            | returns                                             | Description                                                                                                                             |       
  |-----------------------------------------------------------------------------------------------------|-----------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
  | just_of(value: T)                                                                                   | `ResultT[T, Never]`                                 | Wraps the value in a container                                                                                                          |
  | nothing_of()                                                                                        | <nobr>`ResultT[Never, Never]`</nobr>                | Wraps the Nothing                                                                                                                       |
  | error_of(error: E)                                                                                  | `ResultT[Never, E]`                                 | Wraps the error in a container                                                                                                          |
  | maybe_of(maybe: Maybe[T])                                                                           | `ResultT[T, Never]`                                 | Wraps the Maybe value in a container                                                                                                    |
  | result_of(result: Result[T, E])                                                                     | `ResultT[T, E]`                                     | Wraps the Result value in a container                                                                                                   |
  | <nobr>from_null(is_nullable: Callable[[R], bool] = lambda v: v is None)(value: R)</nobr>            | <nobr>`Callable[[R], ResultT[R, Never]]`</nobr>     | Wraps the value based on `is_nullable` predicate                                                                                        | 
  | <nobr>from_try(is_nullable: Callable[[R], bool] = lambda v: v is None)(fn: Callable[..., R])</nobr> | <nobr>`Callable[..., ResultT[R, Exception]]`</nobr> | Decorator. Wraps `fn`, catches possible errors - heirs of `Exception` and wraps the successful result based on `is_nullable` predicate. |
  | <nobr>ap(fn: ResultT[Callable[[T], R], E], val: ResultT[T, E])</nobr>                               | <nobr>`ResultT[R, E]`</nobr>                        | Applies value enclosed in the ResultT to a function also in the ResultT                                                                 |
  | lift2(<br/>fn: Callable[[A1, A2], R],<br/>arg1: ResultT[A1, E],<br/>arg2: ResultT[A2, E]<br/>)      | <nobr>`ResultT[R, E]`</nobr>                        | Applies wrapped values to a two-argument function                                                                                       |
  | lift3, lift4                                                                                        | <nobr>`ResultT[R, E]`</nobr>                        | Similarly to lift2, but for functions with 3 and 4 positional arguments, respectively                                                   |
  | lift(fn: Callable[..., R], *args: ResultT[Any, E])                                                  | <nobr>`ResultT[R, E]`</nobr>                        | Similarly to lift2, but for a function with an arbitrary number of positional arguments                                                 |
### MaybeT methods:
```python
import mafunca.maybe_transformer  # the corresponding module
```
```python
class MaybeT(Generic[T, E]):
    inner: Maybe[Result[T, E]]
```
  | Method(`self` is omitted for brevity)                                                    | returns                        | Description                                                         |          
  |------------------------------------------------------------------------------------------|--------------------------------|---------------------------------------------------------------------|
  | is_ok                                                                                    | `bool`                         | Property - boolean flag                                             |
  | is_error                                                                                 | `bool`                         | Property - boolean flag                                             |
  | is_nothing                                                                               | `bool`                         | Property - boolean flag                                             |
  | <nobr>map(fn: Callable[[T], R])</nobr>                                                   | <nobr>`MaybeT[R, E]`</nobr>    | applies the function, wraps the result                              |
  | <nobr>map_maybe(fn: Callable[[T], Maybe[R]])</nobr>                                      | <nobr>`MaybeT[R, E]`</nobr>    | applies the function, wraps the result                              |
  | <nobr>map_result(fn: Callable[[T], Result[R, E]])</nobr>                                 | <nobr>`MaybeT[R, E]`</nobr>    | applies the function, wraps the result                              |
  | <nobr>bind(fn: Callable[[T], MaybeT[R, E]])</nobr>                                       | <nobr>`MaybeT[R, E]`</nobr>    | applies the function and does not wraps the result                  |
  | <nobr>map_error(fn: Callable[[E], NewE])</nobr>                                          | <nobr>`MaybeT[T, NewE]`</nobr> | mapping the error on a new one                                      |
  | get_or_else(alter: T)                                                                    | extracts or alternative        | extracts the internal value or returns an alternative               |
  | unfold(<br/>*,<br/>just: Callable[[Result[T, E]], R],<br/>nothing: Callable[[], R]<br/>) | `R`                            | extracts the internal value using the corresponding branch function |
### MaybeT additional module functions:
  | Function                                                                                            | returns                                            | Description                                                                                                                             |       
  |-----------------------------------------------------------------------------------------------------|----------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
  | ok_of(value: T)                                                                                     | `MaybeT[T, Never]`                                 | Wraps the value in a container                                                                                                          |
  | error_of(error: E)                                                                                  | <nobr>`MaybeT[Never, E]`</nobr>                    | Wraps the Nothing                                                                                                                       |
  | nothing_of()                                                                                        | <nobr>`MaybeT[Never, Never]`</nobr>                | Wraps the error in a container                                                                                                          |
  | maybe_of(maybe: Maybe[T])                                                                           | `MaybeT[T, Never]`                                 | Wraps the Maybe value in a container                                                                                                    |
  | result_of(result: Result[T, E])                                                                     | `MaybeT[T, E]`                                     | Wraps the Result value in a container                                                                                                   |
  | <nobr>from_null(is_nullable: Callable[[R], bool] = lambda v: v is None)(value: R)</nobr>            | <nobr>`Callable[[R], MaybeT[R, Never]]`</nobr>     | Wraps the value based on `is_nullable` predicate                                                                                        | 
  | <nobr>from_try(is_nullable: Callable[[R], bool] = lambda v: v is None)(fn: Callable[..., R])</nobr> | <nobr>`Callable[..., MaybeT[R, Exception]]`</nobr> | Decorator. Wraps `fn`, catches possible errors - heirs of `Exception` and wraps the successful result based on `is_nullable` predicate. |
  | <nobr>ap(fn: MaybeT[Callable[[T], R], E], val: MaybeT[T, E])</nobr>                                 | <nobr>`MaybeT[R, E]`</nobr>                        | Applies value enclosed in the MaybeT to a function also in the MaybeT                                                                   |
  | lift2(<br/>fn: Callable[[A1, A2], R],<br/>arg1: MaybeT[A1, E],<br/>arg2: MaybeT[A2, E]<br/>)        | <nobr>`MaybeT[R, E]`</nobr>                        | Applies wrapped values to a two-argument function                                                                                       |
  | lift3, lift4                                                                                        | <nobr>`MaybeT[R, E]`</nobr>                        | Similarly to lift2, but for functions with 3 and 4 positional arguments, respectively                                                   |
  | lift(fn: Callable[..., R], *args: MaybeT[Any, E])                                                   | <nobr>`MaybeT[R, E]`</nobr>                        | Similarly to lift2, but for a function with an arbitrary number of positional arguments                                                 |
### Examples
#### An applicative example:
How to chain functions was shown in general terms at the beginning of the section.  
But what about functions with multiple arguments?
```python
def summa(a: int, b: int, c: int) -> int:
    return a + b + c
```
I want to make this function able to apply wrapped values 
and still terminate in a "short-circuit" fashion if one of the arguments is "bad".  
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
from mafunca.curry import curry3

@curry3
def summa(a: int, b: int, c: int) -> int:
    return a + b + c
```

Now, by wrapping the function in the **Ok** container, I can use the **ap** function:

```python
from mafunca.curry import curry3
from mafunca.result import ok_of, err_of, ap


@curry3
def summa(a: int, b: int, c: int) -> int:
    return a + b + c


# NOTE: after each 'ap', a partially applied function is added to the container
ap(ap(ap(ok_of(summa), ok_of(1)), ok_of(2)), ok_of(3))  # Ok(6)

ap(ap(ap(ok_of(summa), err_of("Error")), ok_of(2)), ok_of(3))  # Err("Error")
```
There is a special function to avoid writing such chains manually:

```python
from mafunca.result import ok_of, lift3


def summa(a: int, b: int, c: int) -> int:
    return a + b + c


lift3(summa, ok_of(1), ok_of(2), ok_of(3))  # Ok(6)
```

## Currying
### Description of currying
Examples of currying and the benefits that this approach can provide are given in the section on simple monads - an applicative example.  
The library implements the following curry decorators:
- Simple, 100% typed, for functions with a fixed number of positional arguments
- Powerful, flexible, for functions with arbitrary signatures with the following features:
    - Preserving the signature requirements of the original function (only positional or only named arguments, for example)
    - Fail fast. The incorrectness of the passed arguments is evaluated not at the final call of the original function, but at each step(without calling the original function).
    - Flexible support for default values.
    - Support for variable arguments of the form *args , **kwargs.
    - The ability to use positional and/or named arguments in any quantity or combination.

### Currying examples
#### For functions with a fixed number of positional arguments
```python
from mafunca.curry import curry2, curry3, curry4
```
#### Preserving the signature requirements:
```python
from mafunca.curry import curry

@curry
def for_curry(a, *, b):
    return a + b

# second arg is only named
for_curry(1)(2)    # CurryBadArguments: for_curry - too many positional arguments
for_curry(1)(b=2)  # ok, 3
```
#### Fail fast:
```python
from mafunca.curry import curry

@curry
def for_curry(a, b):
    return a + b

for_curry(c=1)  # CurryBadArguments: for_curry - got an unexpected keyword argument 'c'

```
#### Default values and combinations of positional and named arguments:
```python
from mafunca.curry import curry
@curry
def for_curry(a: int, b: int, c: int = 0, d: int = 0) -> list[int]:
    return [a, b, c, d]

for_curry(1)(2)(3)(4)          # [1, 2, 3, 4]
for_curry(a=1)(b=2)(c=3, d=4)  # [1, 2, 3, 4]

# applying all default values
for_curry(1)(2)()      # [1, 2, 0, 0]
for_curry()(b=2, a=1)  # [1, 2, 0, 0]

# applying default values does not override previously set values(which have defaults)
for_curry(1, 2)(c=3)() # [1, 2, 3, 0]
for_curry(1, 2)(d=3)() # [1, 2, 0, 3]
```
#### Working with *args, **kwargs:
```python
from mafunca.curry import curry

@curry
def for_curry(a: int, b: int, *args, **kwargs) -> list:
    return [a, b, args, kwargs]

res = for_curry(1, b=2)
callable(res)    # True - expects at least one positional and one named argument
res = res(0, 0)  # passing two positional arguments to *args
callable(res)    # True - still waiting for at least one named argument

# passing one named arg and launch original function
res(another=10)       # [1, 2, (0, 0), {'another': 10}]
```

#### Async currying:
```python
import asyncio
from inspect import iscoroutine
from mafunca.curry import curry

@curry
async def for_curry(a: int, b: int, c: int = 0, d: int = 0) -> list[int]:
    await asyncio.sleep(0)
    return [a, b, c, d]


async def main():
    res = for_curry(1)
    res = res(2)
    res = res(3)
    await res(4)  # [1, 2, 3, 4]   


    res = for_curry()
    await res(b=2, a=1)  # [1, 2, 0, 0]

    res = for_curry(1, 2, 3, 4)
    iscoroutine(res)  # True

    await res  # [1, 2, 3, 4]
```


## Effects
### Description of effects
Of course, we will talk about monads again. But this time, we'll be discussing lazy monads.
Laziness means that the calculation will not be performed until its executor is explicitly called.  
Why is this necessary at all?  
A rough example:

```python
from mafunca.effect_sync import Effect, pure, delay
from mafunca.effect_runners import run


def get_addresses_from_database(number: int) -> Effect[list[str]]:
    def get_addresses_from_database_inner() -> list[str]: ...

    # the effect involving number

    return delay(get_addresses_from_database_inner)


def send_emails_via_smtp(addresses: list[str]) -> Effect[None]:
    def send_emails_via_smtp_inner() -> None: ...

    # mailing

    return delay(send_emails_via_smtp_inner)


def function_with_effects(a: int) -> Effect[None]:
    return (
        pure(a ** 2)
        .bind(get_addresses_from_database)
        .bind(send_emails_via_smtp)
    )


effect: Effect[None] = function_with_effects(10)
run(effect)  # performing side effects
```
Despite the fact that the example includes both reading from a database and sending emails,
all functions remain pure because they only describe effects,
but not perform them.  
Well, why is it necessary at all?

The advantages of laziness and pure functions:
- Effects become clearly marked. Function and method signatures become more informative
- You can be sure that calling any function will not cause any side effects until the special executor is called
- By executing effects centrally at a specific level in the code,
  it becomes easier to reason about when the system transitions from state A to state B
- You can test the pure part of the application without fear of causing side effects.
  Even without mock objects

Now let's move on to considering monads for effects.  
Synchronous and asynchronous effects are strictly separated here

### Synchronous effects

```python
from mafunca.effect_sync import Effect
from mafunca.effect_sync import pure, delay, retry, lift2, lift3, lift4

from mafunca.effect_runners import run, run_safe
```
```python
class Effect(Generic[A]): ...
```
#### Effect methods(`self` is omitted for brevity)
| Method                                                                            | returns     | description                                                                                        |
|-----------------------------------------------------------------------------------|-------------|----------------------------------------------------------------------------------------------------|
| map(fn: Callable[[A], B])                                                         | `Effect[B]` | applies the function, wraps the result                                                             |
| <nobr>bind(fn: Callable[[A], Effect[B]])</nobr>                                   | `Effect[B]` | applies the function and does not wraps the result                                                 |  
| <nobr>catch_map(exc_type: type[Exc], catcher: Callable[[Exc], A])</nobr>          | `Effect[A]` | Handler for `Exc` type errors, where `Exc` is a subtype of `Exception`. Wraps the result.          |
| <nobr>catch_bind(exc_type: type[Exc], catcher: Callable[[Exc], Effect[A]])</nobr> | `Effect[A]` | Handler for `Exc` type errors, where `Exc` is a subtype of `Exception`. Does not wraps the result. |
| ensure(finalizer: Effect[None])                                                   | `Effect[A]` | Finalizer                                                                                          |
The methods listed in the table above are only used for binding.  
To initiate an effect, you need to use one of the module-level functions:

| Function                                                                                                                                                                                                                                                                                                                                     | returns     | description                                                                                                                                                  |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| pure(value: A)                                                                                                                                                                                                                                                                                                                               | `Effect[A]` | Wraps a ready-made value                                                                                                                                     |
| <nobr>delay(fn: Callable[[], A])</nobr>                                                                                                                                                                                                                                                                                                      | `Effect[A]` | Wraps a SYNCHRONOUS function for delayed execution                                                                                                           |
| retry(<br/>fn: Callable[[], A],<br/>*,<br/>total_attempts: int = 1,<br/><nobr>pause_seconds_between: Callable[[int], Union[int, float]] = lambda _: 0</nobr>,<br/><nobr>retry_on_result: Callable[[A], bool] = lambda _: False</nobr>,<br/><nobr>retry_on_exceptions: tuple[type[Exception], ...] = ()</nobr>,<br/>step_name: str = ''<br/>) | `Effect[A]` | Wraps a SYNCHRONOUS function for delayed execution. Attempting to repeat it under user-defined conditions. Details can be found in the function's docstring. |
| lift2(<br/>fn: Callable[[A1, A2], R],<br/>arg1: Effect[A1],<br/>arg2: Effect[A2]<br/>)                                                                                                                                                                                                                                                       | `Effect[R]` | Applies wrapped entities to a two-argument function                                                                                                          |
| lift3, lift4                                                                                                                                                                                                                                                                                                                                 | `Effect[R]` | Similarly to lift2, but for functions with 3 and 4 positional arguments, respectively                                                                        |
#### Runners:
- **run(effect)** - simple executor - just runs a chain
- **run_safe(effect)** - runs a chain, catching possible errors - heirs of `Exception`
#### Notes:
If an exception is thrown that is not a subtype of `Exception`, execution will stop immediately,
and the `catch_` and `ensure` methods will not be triggered.  
This remains true even if you set a handler for this exception in the `catch_` method

### Asynchronous effects

```python
from mafunca.effect_async import Aff
from mafunca.effect_async import pure, delay, delay_to_thread, retry, lift2, lift3, lift4

from mafunca.effect_runners import run_async, run_safe_async
```
```python
class Aff(Generic[A]): ...
```
#### Aff methods(`self` is omitted for brevity)
| Method                                                                                                           | returns  | description                                                                                        |
|------------------------------------------------------------------------------------------------------------------|----------|----------------------------------------------------------------------------------------------------|
| map(fn: Callable[[A], B])                                                                                        | `Aff[B]` | applies the function, wraps the result                                                             |
| <nobr>bind(fn: Callable[[A], Aff[B]])</nobr>                                                                     | `Aff[B]` | applies the function and does not wraps the result                                                 |  
| catch_map(<br/><nobr>exc_type: type[Exc],</nobr><br/><nobr>catcher: Callable[[Exc], A]</nobr><br/>)              | `Aff[A]` | Handler for `Exc` type errors, where `Exc` is a subtype of `Exception`. Wraps the result.          |
| catch_bind(<br/><nobr>exc_type: type[Exc],</nobr><br/><nobr>catcher: Callable[[Exc], Aff[A]]</nobr><br/>)</nobr> | `Aff[A]` | Handler for `Exc` type errors, where `Exc` is a subtype of `Exception`. Does not wraps the result. |
| ensure(finalizer: Aff[None])                                                                                     | `Aff[A]` | Finalizer                                                                                          |
The methods listed in the table above are only used for binding.  
To initiate an effect, you need to use one of the module-level functions:

| Function                                                                                                                                                                                                                                                                                                                                                                                                             | returns  | description                                                                                                                                                    |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| pure(value: A)                                                                                                                                                                                                                                                                                                                                                                                                       | `Aff[A]` | Wraps a ready-made value                                                                                                                                       |
| delay(<br/>fn: Callable[[], Awaitable[A]],<br/>wait_seconds: Union[int, float, None] = None<br/>)                                                                                                                                                                                                                                                                                                                    | `Aff[A]` | Wraps an ASYNCHRONOUS function for delayed execution with optional timer                                                                                       |
| <nobr>delay_to_thread(fn: Callable[[], A])</nobr>                                                                                                                                                                                                                                                                                                                                                                    | `Aff[A]` | Wraps a SYNCHRONOUS function for delayed execution in a separate thread                                                                                        |
| retry(<br/>fn: Callable[[], Awaitable[A]],<br/>*,<br/>total_attempts: int = 1,<br/>wait_seconds_on_attempt: Union[int, float, None] = None,<br/><nobr>pause_seconds_between: Callable[[int], Union[int, float]] = lambda _: 0</nobr>,<br/><nobr>retry_on_result: Callable[[A], bool] = lambda _: False</nobr>,<br/><nobr>retry_on_exceptions: tuple[type[Exception], ...] = ()</nobr>,<br/>step_name: str = ''<br/>) | `Aff[A]` | Wraps an ASYNCHRONOUS function for delayed execution. Attempting to repeat it under user-defined conditions. Details can be found in the function's docstring. |
| lift2(<br/>fn: Callable[[A1, A2], R],<br/>arg1: Aff[A1],<br/>arg2: Aff[A2]<br/>)                                                                                                                                                                                                                                                                                                                                     | `Aff[R]` | Applies wrapped entities to a two-argument function                                                                                                            |
| lift3, lift4                                                                                                                                                                                                                                                                                                                                                                                                         | `Aff[R]` | Similarly to lift2, but for functions with 3 and 4 positional arguments, respectively                                                                          |
#### Runners:
- **run_async(effect)** - awaitable simple executor - just runs a chain
- **run_safe_async(effect)** - awaitable, runs a chain, catching possible errors - heirs of `Exception` or `TimeoutError`
#### Notes:
- Everything that was described in a similar section for synchronous effects remains valid here,
  except for `asyncio.CancelledError`.  
  The library is available for python >= 3.11, and in these versions, `asyncio.CancelledError` is not a subtype of `Exception`.  
  However, `ensure` will be executed when an `asyncio.CancelledError` is thrown.  
  But if an error occurs in `ensure` itself, it will not replace the `asyncio.CancelledError` and will be lost.  
  Moreover, if you catch `asyncio.CancelledError` in `catch_` methods, despite the types in the signature and the fact that this is not recommended,
  the error will actually be caught.
- Although this is a monad for asynchronous effects, asynchrony is only allowed in the `delay` and `retry` nodes. 
  These nodes are the initiators of the effect, while the rest are either pure computations or pure transitions to the next effects.
- `delay_to_thread` does not have a timer because there is no reliable way to cancel a running thread.

### Transformers
Each effect monad has its own transformer over Result

```python
from mafunca.effect_sync_transformer import EffectResult
from mafunca.effect_sync_transformer import pure, delay, retry
from mafunca.effect_sync_transformer import lift_error, lift_result, lift_effect
from mafunca.effect_sync_transformer import lift2, lift3, lift4
```
```python
class EffectResult(Generic[A, E]):    
    inner: Effect[Result[A, E]]
```

```python
from mafunca.effect_async_transformer import AffResult
from mafunca.effect_async_transformer import pure, delay, delay_to_thread, retry
from mafunca.effect_async_transformer import lift_error, lift_result, lift_effect
from mafunca.effect_async_transformer import lift2, lift3, lift4
```
```python
class AffResult(Generic[A, E]):    
    inner: Aff[Result[A, E]]
```
The performers are the same:
```python
from mafunca.effect_runners import run, run_safe, run_async, run_safe_async
```
Transformers have the same set of binding methods, plus:
- `map_result`
- `map_error`
- `catch_map_result`

The purpose of additional functions and methods is easily readable from their signatures,
so they are not described here.

Also, note that the `ensure` methods expect finalizers of the **original effect type**,
not the transformer type.

### General remarks
- Effect monads are stack-safe, so you can build chains of any length and nesting. 
- When the `retry` node runs out of attempts to retry based on exceptions or a predicate,
  exceptions `RetryByExceptionError` and `RetryByValueError` are thrown, respectively.
  You can always catch them with `catch_` methods and extract, for example,
  the successful result preceding the `retry` node and/or the value that did not satisfy the predicate.
- Be careful with the scopes for the `catch_` and `ensure` methods, for example:
```python
from mafunca.effect_sync import delay


effect = (
  delay(open_resource)
  .bind(lambda resource: (
      delay(hanble_resource)
      .catch_map(SomeDomainError, catcher)
      .ensure(close_resource)
  ))
  .ensure(delay(logging))
)
```
Here, `ensure(delay(logging))` will always be executed.  
But if an error occurs in `open_resource`,
then the `catch_map` and `ensure` inside the `bind` method will not be executed, because  
they are not yet added to the continuation stack at the time of `open_resource` execution, only the general lambda function from `bind` is added.

### Effect examples
The examples are "toy-like", but they reflect the essence

```python
from mafunca.effect_async import Aff, pure, retry
from mafunca.effect_runners import run_async


def example_retry() -> Aff[int]:
  glb = 0

  def effect(value):
    async def effect_inner():
      nonlocal glb
      glb += 1
      if glb < 3:
        raise TypeError("Example error")
      return value

    return effect_inner

  eff = (
    pure(0)
    .map(lambda v: v + 1)
    .bind(lambda v: retry(
      effect(v),
      total_attempts=3,
      retry_on_exceptions=(TypeError,)
    ))
  )
  return eff


async def main():
  eff = example_retry()
  res = await run_async(eff)  # 1
  return res
```


## Exceptions
### Description of exceptions
```python
import mafunca.common.exceptions
```
- `MonadError(BaseException)` - thrown when monadic contracts are violated. It is not recommended to catch.  
  Separated - not in the error hierarchy of this library.
- `MafuncaBaseError(Exception)` - base library level exception
- `CurryBadFunctionError(MafuncaBaseError)` - thrown when the 'curried' function is not suitable
- `CurryBadArguments(MafuncaBaseError)` - thrown when the passed arguments for the function are incorrect
- `ValidationError(MafuncaBaseError)` - an error thrown during validation of parameters.
  For example, in the retry nodes.
- `RetryByExceptionError(MafuncaBaseError)` - thrown when attempts are exhausted by exception for nodes with retries.  
  Contains the following attributes:
  - `previous_result` - the result of the step preceding the `retry` node
  - `previous_result_is_assigned` - `False` if the `retry` node is the first in the chain
  - `exception` - the exception for which repeats were made
  - `step_name` - name of the step
- `RetryByValueError(MafuncaBaseError)` - thrown when attempts are exhausted by predicate for nodes with retries.  
  Contains the following attributes:
  - `previous_result` - the result of the step preceding the `retry` node
  - `previous_result_is_assigned` - `False` if the `retry` node is the first in the chain
  - `current_result` - a value that did not satisfy the predicate function
  - `step_name` - name of the step
- `RetryBadPauseError(MafuncaBaseError)` - thrown when there is an incorrect pause between attempts
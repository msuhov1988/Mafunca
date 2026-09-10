[![PyPI version](https://img.shields.io/pypi/v/mafunca.svg)](https://pypi.org/project/mafunca/)
[![Python versions](https://img.shields.io/pypi/pyversions/mafunca.svg)](https://pypi.org/project/mafunca/)
[![License](https://img.shields.io/pypi/l/mafunca.svg)](https://pypi.org/project/mafunca/)
## For version <=0.5.3, see old_docs_0_5_3.md
## For version <=0.8.3, see old_docs_0_8_3.md

### Mafunca is a small FP library with a practical focus.
### Rather than trying to implement every functional abstraction, it concentrates on a few useful ideas: 
- ### make failures explicit
- ### avoid scattering `None` checks across the codebase
- ### describe side effects lazily, so programs can be composed without performing them immediately
### The library is dependency-free and provides a stack-safe effect system with explicit execution, contract validation and deliberately separate synchronous and asynchronous runtimes.
### The effect system also supports composable error handling, scoped finalization and retry semantics.

### [Installiation](#installation)
- [Install mafunca](#install-mafunca)

### [Error handling and missing values](#error-handling-and-missing-values)
- [Description](#description)
- [Modules](#modules)
- [Constructors](#constructors)
- [Chaining functions](#chaining-functions)
- [Multiple arguments](#multiple-arguments)
- [Table of functions](#table-of-functions)
- [Remarks](#remarks)
- [Example](#example)

### [Currying](#currying)
- [Description of currying](#description-of-currying)
- [Currying examples](#currying-examples)

### [Effects](#effects)
- [Description of effects](#description-of-effects)
- [Modules of effects](#modules-of-effects)
- [Constructors of effects](#constructors-of-effects)
- [Functions table](#functions-table)
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
What we want to get: 
- Transfer errors and missing values to the types
- To ensure that the next step is not executed if the current one ends in an error / absence of a value. 
- Maintain the linearity of the execution flow

Let’s define the basic containers and union types: 
- Success or failure
```python
from dataclasses import dataclass
from typing import TypeVar, Generic, TypeAlias

T= TypeVar("T", covariant=True)
E = TypeVar("E", covariant=True)

@dataclass(frozen=True, slots=True, repr=True)
class Success(Generic[T]):
    value: T


@dataclass(frozen=True, slots=True, repr=True)
class Fail(Generic[E]):
    error: E

Result: TypeAlias = Success[T] | Fail[E]
``` 
- There is a value or there is no value
```python
from dataclasses import dataclass
from typing import TypeVar, Generic, TypeAlias

T = TypeVar("T", covariant=True)

@dataclass(frozen=True, slots=True, repr=True)
class Just(Generic[T]):
    value: T


@dataclass(frozen=True, slots=True, repr=True)
class Nothing:
    pass

Maybe: TypeAlias = Just[T] | Nothing
```
Thus, we obtain the following closed union types:
- `Result[T, E]`
- `Maybe[T]` 

If all three states are needed at once, here transformers:
- `ResultMaybe: TypeAlias = Result[Maybe[T], E]`
- `MaybeResult: TypeAlias = Maybe[Result[T, E]]`
- сhoose the form that suits you best

Thus, we have the types.  
All that remains is to define special functions for working with them 
so that all the requirements from the list of wishes are met.  
More on this below.

Why union types, and not, for example, classes?
- type narrowing based on conditions and branching works well
- pattern matching becomes natural
- the analyzers will check that all states have been processed


### Modules

For each of the types listed in the previous point, several modules have been implemented:
- basic functions and constructors
```python
import mafunca.result
import mafunca.maybe
import mafunca.result_trans
import mafunca.maybe_trans
```
- chaining functions in a direct form
```python
import mafunca.result.direct
import mafunca.maybe.direct
import mafunca.result_trans.direct
import mafunca.maybe_trans.direct
```
- chaining functions in a flow‑based form
```python
import mafunca.result.flow
import mafunca.maybe.flow
import mafunca.result_trans.flow
import mafunca.maybe_trans.flow
```
- for working with functions of multiple arguments
```python
import mafunca.result.lift
import mafunca.maybe.lift
import mafunca.result_trans.lift
import mafunca.maybe_trans.lift
```

### Constructors:
```python
from mafunca.result import Result, success, fail, is_success, is_fail, from_try

r1 = success(1)  # Result[int, Never]
r2 = fail(0)     # Result[Never, int]

is_success(r1)   # True, the type narrows
is_fail(r2)      # True, the type narrows

def divide_safe(a: int, b: int) -> Result[float, ZeroDivisionError]:
    try:
        return success(a / b)
    except ZeroDivisionError as err:
        return fail(err)

@from_try
def divide_unsafe(a: int, b: int) -> float:
    return a / b

r3 = divide_safe(10, 2)
print(r3)  # Success(value=5.0)
r4 = divide_safe(10, 0)
print(r4)  # Fail(error=ZeroDivisionError('division by zero'))

r5 = divide_unsafe(10, 2)
print(r5)  # Success(value=5.0)
r6 = divide_unsafe(10, 0)
print(r6)  # Fail(error=ZeroDivisionError('division by zero'))
```

```python
from mafunca.maybe import Maybe, just, nothing, is_just, is_nothing, from_null

r1 = just(1)    # Maybe[int]
r2 = nothing()  # Maybe[Never]

is_just(r1)     # True, the type narrows
is_nothing(r2)  # True, the type narrows


r3 = from_null(1)
print(r3)  # Just(value=1)

r4 = from_null(None)
print(r4)  # Nothing()

r5 = from_null([], lambda lst: len(lst) == 0)
print(r5)  # Nothing()
```

```python
import mafunca.result as result
import mafunca.maybe as maybe

from mafunca.result_trans import ResultMaybe, success, fail, nothing
from mafunca.result_trans import is_success, is_fail, is_nothing
from mafunca.result_trans import lift_maybe, lift_result
from mafunca.result_trans import from_try, from_null

r1 = success(1)  # ResultMaybe[int, Never]
r2 = fail(0)     # ResultMaybe[Never, int]
r3 = nothing()   # ResultMaybe[Never, Never]

is_success(r1)  # True, the type narrows
is_fail(r2)     # True, the type narrows
is_nothing(r3)  # True, the type narrows

r4 = lift_maybe(maybe.just(1))    # ResultMaybe[int, Never]
r5 = lift_maybe(maybe.nothing())  # ResultMaybe[Never, Never]

r6 = lift_result(result.success(1))  # ResultMaybe[int, Never]
r7 = lift_result(result.fail(0))     # ResultMaybe[Never, int]

def divide_triple(a: int, b: int) -> ResultMaybe[float, ZeroDivisionError]:
    try:
        return nothing() if a < 0 else success(a / b)
    except ZeroDivisionError as err:
        return fail(err)

@from_try
def divide_unsafe(a: int, b: int) -> float:
    return a / b

print(divide_triple(10, 5))   # Success(value=Just(value=2.0))
print(divide_triple(-10, 2))  # Success(value=Nothing())
print(divide_triple(10, 0))   # Fail(error=ZeroDivisionError('division by zero'))

print(from_null(1))                                    # Success(value=Just(value=1))  
print(from_null(None))                                 # Success(value=Nothing())
print(from_null([], lambda lst: len(lst) == 0))        # Success(value=Nothing())
```

```python
import mafunca.result as result
import mafunca.maybe as maybe

from mafunca.maybe_trans import MaybeResult, just, fail, nothing
from mafunca.maybe_trans import is_just, is_fail, is_nothing
from mafunca.maybe_trans import lift_maybe, lift_result
from mafunca.maybe_trans import from_try, from_null

# Similarly to the ResultMaybe transformer
# The only difference is in the resulting type.
```
Recommendations:
- Do not directly use the `Success, Fail, Just, Nothing` classes to create values.  
  Use the corresponding constructor functions.  
  Otherwise, type checkers may complain about generics for which types are not defined.
- Instead of transformers, it is preferable to use a simple `Result`,  
  simulating the 'nothing' with some kind of special error

### Chaining functions
When listing the functions, I will indicate in parentheses the containers for which there is an implementation.  
But I’ll provide examples only for one of them.  
Because their mechanics are similar; the only difference is in the types of arguments.

- `fmap (all)` - applies the function and wraps the result. As a rule, the applied function returns a non‑monadic value
```python
from mafunca.result import success, fail
from mafunca.result.direct import fmap as map_direct
from mafunca.result.flow import fmap as map_flow

from mafunca.flow import flow

r1 = map_direct(success(0), lambda v: v + 1)               # Success(value=1)
r2 = flow(success(0), map_flow(lambda v: v + 1))           # Success(value=1)
r3 = flow(success(0), map_flow(lambda v: success(v + 1)))  # Success(value=Success(value=1)), always wraps!
r4 = flow(fail(0), map_flow(lambda v: v + 1))              # Fail(error=0)
```
- `fmap_error (Result, ResultMaybe, MaybeResult)` - error transformation
```python
from mafunca.result import success, fail
from mafunca.result.direct import fmap_error as emap_direct
from mafunca.result.flow import fmap_error as emap_flow

from mafunca.flow import flow

r1 = emap_direct(fail(1), lambda v: f'error_code: {v}')         # Fail(error='error_code: 1')
r2 = flow(fail(1), emap_flow(lambda v: f'error_code: {v}'))     # Fail(error='error_code: 1')
r3 = flow(success(1), emap_flow(lambda v: f'error_code: {v}'))  # Success(value=1)
```
- `bind (all)` - the function being applied must return a monad of the same type
```python
from mafunca.result import success, fail
from mafunca.result.direct import bind as bind_direct
from mafunca.result.flow import bind as bind_flow

from mafunca.flow import flow

r1 = bind_direct(success(1), lambda v: success(v + 1))   # Success(value=2)
r2 = flow(success(1), bind_flow(lambda v: fail(0)))      # Fail(error=0)
r3 = flow(fail(0), bind_flow(lambda v: success(v + 1)))  # Fail(error=0)
```
- `fold (all)` - extraction based on the passed functions
```python
from mafunca.result import success, fail
from mafunca.result.direct import fold as fold_direct
from mafunca.result.flow import fold as fold_flow

from mafunca.flow import flow

r1 = fold_direct(success(1), on_success=lambda v: v + 1, on_fail=lambda _: 0)  # 2
r2 = flow(
    fail(1),
    fold_flow(on_success=lambda v: v + 1, on_fail=lambda e: e - 1)
)  # 0
```
- `get_or_else (all)` - extraction or default return
```python
from mafunca.result import success, fail
from mafunca.result.direct import get_or_else as get_direct
from mafunca.result.flow import get_or_else as get_flow

from mafunca.flow import flow

r1 = get_direct(success(1), 10)   # 1
r2 = flow(fail(1), get_flow(10))  # 10
```
- `ap (all)` - working with functions of multiple arguments that allow partial application
```python
from mafunca.result import success, fail
from mafunca.result.direct import ap as ap_direct
from mafunca.result.flow import ap as ap_flow

from mafunca.flow import flow

def collect(a: int):
    def collect_1(b: int):
        def collect_2(c: int):
            return [a, b, c]
        return collect_2
    return collect_1

partial1 = ap_direct(success(1), success(collect))
partial2 = ap_direct(success(2), partial1)
r1 = ap_direct(success(3), partial2)  # Success(value=[1, 2, 3])

r2 = flow(
    success(collect), 
    ap_flow(success(1)), 
    ap_flow(success(2)), 
    ap_flow(fail(3))
)  # Fail(error=3)
```

Transformers have two additional functions:
- `fmap_maybe`
- `fmap_result`  
As you might guess, they are similar to `fmap`, but applied function must return `Maybe` and `Result`, respectively.

### Multiple arguments
More convenient analogues of `ap` for working with functions that have multiple positional arguments.
```python
from mafunca.result import success, fail
from mafunca.result.lift import lift2, lift3, lift4, lift


def collect2(a: int, b: int):    
    return [a, b]

def collect3(a: int, b: int, c: int):    
    return [a, b, c]

def collect4(a: int, b: int, c: int, d: int):    
    return [a, b, c, d]

def collect_n(*args: int):    
    return [*args]

r2 = lift2(collect2, success(1), success(2))                       # Success(value=[1, 2])
r3 = lift3(collect3, success(1), success(2), fail(0))              # Fail(error=0)
r4 = lift4(collect4, fail(1), success(2), success(3), success(4))  # Fail(error=1)

kit = [success(i) for i in range(10)]
rn = lift(collect_n, *kit)  # Success(value=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
```

### Table of functions
| Function      | Module       | Result | Maybe | ResultMaybe | MaybeResult |
|---------------|--------------|--------|-------|-------------|-------------|
| `fmap`        | direct, flow | +      | +     | +           | +           |
| `fmap_error`  | direct, flow | +      |       | +           | +           |
| `fmap_maybe`  | direct, flow |        |       | +           | +           |
| `fmap_result` | direct, flow |        |       | +           | +           |
| `bind`        | direct, flow | +      | +     | +           | +           |
| `fold`        | direct, flow | +      | +     | +           | +           |
| `get_or_else` | direct, flow | +      | +     | +           | +           |
| `ap`          | direct, flow | +      | +     | +           | +           |
| `lift2 `      | lift         | +      | +     | +           | +           |
| `lift3`       | lift         | +      | +     | +           | +           |
| `lift4`       | lift         | +      | +     | +           | +           |
| `lift`        | lift         | +      | +     | +           | +           |

### Example
Let’s expand the humorous example with safe division:
```python
from mafunca.result import from_try, success, fail, Result
from mafunca.result.flow import fmap, bind
from mafunca.flow import flow

@from_try
def divide_unsafe(a: int, b: int) -> int:
    return int(a / b)


def only_even_numbers(a: int) -> Result[int, Exception]:
    if a % 2 == 0:
        return success(a)
    return fail(ValueError(f'An even number was expected, but {a} received'))


def strange_handler(a: int, b: int):
    # We convert functions that can return errors into the Result channel.
    # Thanks to the chaining functions, all errors are linearly propagated to the end of the chain.
    # no checks, no external try except, etc. 

    return flow(
        divide_unsafe(a, b),
        fmap(lambda v: v + 1),
        bind(only_even_numbers),
        fmap(lambda v: v ** 2),
    )


r1 = strange_handler(10, 2)  # Success(value=36)
r2 = strange_handler(10, 0)  # Fail(error=ZeroDivisionError('division by zero'))
r3 = strange_handler(4, 2)   # Fail(error=ValueError('An even number was expected, but 3 received'))
```

### Remarks
All of this applies only to pure functions without side effects.  
If you need side effects or asynchrony, look at the effects.  


## Currying
### Description of currying
  
The library implements the following curry decorators:
- Simple, 100% typed, for functions with a fixed number of positional arguments
- Powerful, flexible, but, unfortunately, not typed, for functions with arbitrary signatures with the following features:
    - Preserving the signature requirements of the original function (only positional or only named arguments, for example)
    - Fail fast. The incorrectness of the passed arguments is evaluated not at the final call of the original function, but at each step(without calling the original function).
    - Flexible support for default values.
    - Support for variable arguments of the form *args , **kwargs.
    - The ability to use positional and/or named arguments in any quantity or combination.

### Currying examples
```python
from mafunca.curry import curry2, curry3, curry4  # fixed and typed
from mafunca.curry import curry                   # flexible, but not typed
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
Here we will discuss types and constructions with a lazy execution model.
Laziness means that the calculation will not be performed until its executor is explicitly called.  
Why is this necessary at all?  
A rough example:

```python
from mafunca.eff import Eff, pure, delay
from mafunca.eff.flow import bind
from mafunca.effect_runners import run
from mafunca.flow import flow

def get_addresses_from_database(number: int) -> Eff[list[str]]:
    def get_addresses_from_database_inner() -> list[str]: ...
        # ... some operation with side effects involving number
    return delay(get_addresses_from_database_inner)


def send_emails_via_smtp(addresses: list[str]) -> Eff[None]:
    def send_emails_via_smtp_inner() -> None: ...
    # ... mailing
    return delay(send_emails_via_smtp_inner)


def function_with_effects(a: int) -> Eff[None]:
    return flow(
        pure(a ** 2),
        bind(get_addresses_from_database),
        bind(send_emails_via_smtp)
    )

effect = function_with_effects(10)
run(effect)  # performing side effects
```
Despite the fact that the example includes both reading from a database and sending emails,
all functions remain pure because they only describe effects,
but not perform them.  

The advantages of laziness and pure functions:
- Effects become clearly marked. Function and method signatures become more informative
- You can be sure that calling any function will not cause any side effects until the special executor is called
- By executing effects centrally at a specific level in the code,
  it becomes easier to reason about when the system transitions from state A to state B
- You can test the pure part of the application without fear of causing side effects.
  Even without mock objects

The effects implemented here have a number of features: 
- Stack safety
- Synchronous and asynchronous effects are strictly separated
- Even in async effects, asynchrony is permissible only in certain nodes.  
  Chaining functions must be synchronous
- The ability to configure retries for a specific node in the chain
- The ability to asynchronously perform blocking IO in a separate thread (for async effects only)
- Built‑in exception handlers and finalizers

Now let's move on to considering types and constructions.  
The approach is similar:  
- there are basic classes and types  
- there are separate functions for working with them.
```python
from mafunca.eff import Eff  # for synchronous effects
from mafunca.aff import Aff  # for asynchronous effects
```
And the transformers:
- `EffResult: TypeAlias = Eff[Result[T, E]]`
- `AffResult: TypeAlias = Aff[Result[T, E]]`


### Modules of effects
The structure of the modules here is similar.
- basic functions and constructors
```python
import mafunca.eff
import mafunca.eff_trans

import mafunca.aff
import mafunca.aff_trans
```
- chaining functions in a direct form
```python
import mafunca.eff.direct
import mafunca.eff_trans.direct

import mafunca.aff.direct
import mafunca.aff_trans.direct
```
- chaining functions in a flow‑based form
```python
import mafunca.eff.flow
import mafunca.eff_trans.flow

import mafunca.aff.flow
import mafunca.aff_trans.flow
```
- for working with functions of multiple arguments
```python
import mafunca.eff.lift
import mafunca.eff_trans.lift

import mafunca.aff.lift
import mafunca.aff_trans.lift
```

### Constructors of effects
```python
from mafunca.eff import Eff, pure, delay, retry
from mafunca.effect_runners import run, run_safe


eff1 = pure(1)           # Eff[int]
eff2 = delay(lambda: 1)  # Eff[int]  

# The ability to configure retries for a specific node in the effects chain.
# Additional parameters and their values are described in the function’s docstring.
eff3 = retry(lambda: 1)  # Eff[int]

r1 = run(eff1)  # 1
r2 = run(eff2)  # 1
r3 = run(eff3)  # 1

# Executing the effect with error(subclasses of Exception) handling.
# This runner always returns Result[T, Exception] for Eff[T].
r4 = run_safe(eff1)  # Success(value=1)
r5 = run_safe(eff2)  # Success(value=1)
r6 = run_safe(eff3)  # Success(value=1)
``` 
```python
from mafunca.eff_trans import EffResult, pure_success, pure_fail, pure_result, lift_effect
from mafunca.eff_trans import delay, retry
from mafunca.effect_runners import run, run_safe

from mafunca.result import success, fail
from mafunca.eff import delay as eff_delay


eff1 = pure_success(1)                                                # EffResult[int, Never]
eff2 = pure_fail(0)                                                   # EffResult[Never, int]
eff3 = pure_result((lambda a: success(a) if a >= 0 else fail(a))(0))  # EffResult[int, int]

origin_delay = eff_delay(lambda: 1)  # Eff[int]
eff4 = lift_effect(origin_delay)     # EffResult[int, Never]

eff5 = delay(lambda: fail(1))     # EffResult[Never, int]  
eff6 = retry(lambda: success(1))  # EffResult[int, Never]

r1 = run(eff6)       # Success(value=1)

# returns Result[Result[T, E], Exception] for EffResult[T, E]
r2 = run_safe(eff6)  # Success(value=Success(value=1))
```
```python
import asyncio
from time import sleep

from mafunca.aff import Aff, pure, delay, delay_to_thread, retry
from mafunca.effect_runners import run_async, run_safe_async

async def unblocking() -> int:
    await asyncio.sleep(1)
    return 1

def blocking():
    sleep(1)
    return 1

eff1 = pure(1)                           # Aff[int]
eff2 = delay(unblocking, wait_seconds=2) # Aff[int] 

# executing blocking IO in a separate thread, no timers.
eff3 = delay_to_thread(blocking)  # Aff[int]  

# The ability to configure retries for a specific node in the effects chain.
# Additional parameters and their values are described in the function’s docstring.
eff4 = retry(unblocking)  # Aff[int]

async def main():
    r1 = await run_async(eff1)  # 1    
    r2 = await run_async(eff2)  # 1    
    r3 = await run_async(eff3)  # 1    
    r4 = await run_async(eff4)  # 1 

    # Executing the effect with error handling — subclasses of Exception.
    # This runner always returns Result[T, Exception] for Eff[T].
    r5 = await run_safe_async(eff1)  # Success(value=1)   
    r6 = await run_safe_async(eff2)  # Success(value=1)
    r7 = await run_safe_async(eff3)  # Success(value=1)
    r8 = await run_safe_async(eff4)  # Success(value=1)

asyncio.run(main())
```
```python
import asyncio
from time import sleep
from typing import Never

from mafunca.aff_trans import AffResult, pure_success, pure_fail, pure_result, lift_effect
from mafunca.aff_trans import delay, delay_to_thread, retry
from mafunca.effect_runners import run_async, run_safe_async

from mafunca.result import Result, success, fail
from mafunca.aff import delay as aff_delay

async def unblocking() -> int:
    await asyncio.sleep(1)
    return 1

async def unblocking_result() -> Result[int, Never]:
    await asyncio.sleep(1)
    return success(1)

def blocking_result() -> Result[int, Never]:
    sleep(1)
    return success(1)

eff1 = pure_success(1)                                                # AffResult[int, Never]
eff2 = pure_fail(0)                                                   # AffResult[Never, int]
eff3 = pure_result((lambda a: success(a) if a >= 0 else fail(a))(0))  # AffResult[int, int]

origin_delay = aff_delay(unblocking, wait_seconds=2)  # Aff[int]
eff5 = lift_effect(origin_delay)                      # AffResult[int, Never]

eff6 = delay(unblocking_result, wait_seconds=2)  # AffResult[int, Never]
eff7 = delay_to_thread(blocking_result)          # AffResult[int, Never]  
eff8 = retry(unblocking_result)                  # AffResult[int, Never]

async def main():
    r1 = await run_async(eff8)       # Success(value=1)
    
    # returns Result[Result[T, E], Exception] for AffResult[T, E]
    r2 = await run_safe_async(eff8)  # Success(value=Success(value=1))

asyncio.run(main())
```

### Functions table
Functions for effects work similarly to functions for Result, Maybe, etc.  
The only difference is in the types, which are easily readable from the signatures.
Therefore, only a brief table listing them is provided here.

| Function            | Module       | Eff | EffResult | Aff | AffResult |
|---------------------|--------------|-----|-----------|-----|-----------|
| `fmap`              | direct, flow | +   | +         | +   | +         |
| `fmap_error`        | direct, flow |     | +         |     | +         |
| `fmap_result`       | direct, flow |     | +         |     | +         |
| `bind`              | direct, flow | +   | +         | +   | +         |
| `catch_fmap`        | direct, flow | +   | +         | +   | +         |
| `catch_fmap_result` | direct, flow |     | +         |     | +         |
| `catch_bind`        | direct, flow | +   | +         | +   | +         |
| `ensure `           | direct, flow | +   | +         | +   | +         |
| `ap`                | direct, flow | +   | +         | +   | +         |
| `lift2`             | lift         | +   | +         | +   | +         |
| `lift3`             | lift         | +   | +         | +   | +         |
| `lift4`             | lift         | +   | +         | +   | +         |

### General remarks
Since the effects here have built‑in error handlers and finalizers, it’s worth mentioning some of their features:
- If an exception is thrown that is not a subtype of `Exception`, execution will stop immediately,  and the `catch_` and `ensure` steps will not be triggered.  
  This remains true even if you set a handler for this exception in the `catch_`, despite the types.  
  However, for `asyncio.CancelledError` everything works differently in asynchronous case.  
  `ensure` will be executed when an `asyncio.CancelledError` is thrown.  
- The error in `ensure` works similarly to that in `finally` — it replaces the current error (if any) and adds it to its own context.  
  But if the current error is `asyncio.CancelledError`, then it is not replaced.  
  Because the cancellation signal is considered to be of higher priority.
- If you catch `asyncio.CancelledError` in `catch_` methods, despite the types in the signature and the fact that this is not recommended, the error will actually be caught.
- Be careful with the scopes for the `catch_` and `ensure` methods, for example:
```python
from mafunca.eff import delay
from mafunca.eff.flow import bind, catch_fmap, ensure
from mafunca.flow import flow

effect = flow(
  delay(open_resource),
  bind(lambda src: flow(
      delay(lambda: handle_resource(src)),
      catch_fmap(SomeDomainError, catcher),
      ensure(delay(lambda: close(src)))
  )),
  ensure(delay(logging))
)
```
  Here, `ensure(delay(logging))` will always be executed.  
  But if an error occurs in `open_resource`, then the `catch_map` and `ensure` inside the `bind` will not be executed.  
  Because the top-level effect, which includes `open_resource`, consists of three steps:  
- delay(open_resource)
- a function in bind
- ensure(delay_logging)

While `catch_` and `ensure` inside `bind` are related to an internal effect and are limited to its scope.
  

Other remarks:
- Effect monads are stack-safe, so you can build chains of any length and nesting. 
- When the `retry` node runs out of attempts to retry based on exceptions or a predicate,
  exceptions `RetryByExceptionError` and `RetryByValueError` are thrown, respectively.
  You can always catch them with `catch_` methods and extract, for example,
  the successful result preceding the `retry` node and/or the value that did not satisfy the predicate.
- Asynchronous effects: asynchrony is only allowed in the `delay` and `retry` nodes.  
  These nodes are the initiators of the effect, while the rest are either pure computations or pure transitions to the next effects.
- `delay_to_thread` does not have a timer because there is no reliable way to cancel a running thread.



### Effect examples
The examples are "toy-like", but they reflect the essence

```python
import asyncio

from mafunca.aff import Aff, pure, retry
from mafunca.aff.flow import fmap, bind
from mafunca.flow import flow
from mafunca.effect_runners import run_async

def example_retry() -> Aff[int]:
    glb = 0

    def effect(value: int):

        async def effect_inner():
            nonlocal glb
            glb += 1
            if glb < 3:
                raise TypeError("Example error")
            return value

        return effect_inner

    eff = flow(
        pure(0),
        fmap(lambda v: v + 1),
        bind(lambda v: retry(
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

asyncio.run(main())
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
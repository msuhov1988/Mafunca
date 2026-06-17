import inspect
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Union

from mafunca.common.exceptions import CurryBadFunctionError, CurryBadArguments


__all__ = [
    'curry2',
    'curry3',
    'curry4',
    'curry',
]


A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")
D = TypeVar("D")
R = TypeVar("R")


def curry2(fn: Callable[[A, B], R]) -> Callable[[A], Callable[[B], R]]:
    """
        Currying decorator for a function with TWO POSITIONAL arguments.
    """
    def curry2_step1(arg1: A) -> Callable[[B], R]:

        def curry2_final(arg2: B) -> R:
            return fn(arg1, arg2)

        return wraps(fn)(curry2_final)

    return curry2_step1


def curry3(fn: Callable[[A, B, C], R]) -> Callable[[A], Callable[[B], Callable[[C], R]]]:
    """
        Currying decorator for a function with THREE POSITIONAL arguments.
    """
    def curry3_step1(arg1: A) -> Callable[[B], Callable[[C], R]]:

        def curry3_step2(arg2: B) -> Callable[[C], R]:

            def curry3_final(arg3: C) -> R:
                return fn(arg1, arg2, arg3)
            return wraps(fn)(curry3_final)

        return curry3_step2

    return curry3_step1


def curry4(fn: Callable[[A, B, C, D], R]) -> Callable[[A], Callable[[B], Callable[[C], Callable[[D], R]]]]:
    """
        Currying decorator for a function with FOUR POSITIONAL arguments.
    """
    def curry4_step1(arg1: A) -> Callable[[B], Callable[[C], Callable[[D], R]]]:

        def curry4_step2(arg2: B) -> Callable[[C], Callable[[D], R]]:

            def curry4_step3(arg3: C) -> Callable[[D], R]:

                def curry4_final(arg4: D) -> R:
                    return fn(arg1, arg2, arg3, arg4)

                return wraps(fn)(curry4_final)

            return curry4_step3

        return curry4_step2

    return curry4_step1


def _extract_name(func) -> str:
    return getattr(func, "__qualname__", getattr(func, "__name__", f"{func}"))


def _panic_on_bad_curried(func):
    """
       Panic on improper entity for currying.
       :raises CurryBadFunctionError:
    """
    if not callable(func):
        raise CurryBadFunctionError(func_name=_extract_name(func), err="must be a callable object")
    if inspect.isbuiltin(func):
        raise CurryBadFunctionError(func_name=_extract_name(func), err="should not be a built-in function")
    if inspect.ismethod(func):
        raise CurryBadFunctionError(func_name=_extract_name(func), err="should not be a bound method")


def _apply(sig: inspect.Signature, *args, **kwargs) -> inspect.BoundArguments:
    """
        Applying arguments to a function signature.
        :raises TypeError: error of 'bind_partial' method.
    """
    bound_args = sig.bind_partial(*args, **kwargs)
    if len(args) == 0 and len(kwargs) == 0:
        bound_args.apply_defaults()
        for name, par in sig.parameters.items():
            if par.kind == inspect.Parameter.VAR_KEYWORD or par.kind == inspect.Parameter.VAR_POSITIONAL:
                bound_args.arguments.pop(name, None)
    return bound_args


def _curry_step(fn, signature, positioned_args, named_args) -> Callable[..., Union[Callable, R]]:
    def _curry_step_inner(*args, **kwargs) -> Union[Callable, R]:
        try:
            bound_args = _apply(signature, *args, **kwargs)
            new_params = [par for name, par in signature.parameters.items() if name not in bound_args.arguments]
            if len(new_params) == 0:
                return fn(*positioned_args, *bound_args.args, **named_args, **bound_args.kwargs)

            new_sig = inspect.Signature(parameters=new_params)
            new_pos = [*positioned_args, *bound_args.args]
            new_named = {**named_args, **bound_args.kwargs}
            return _curry_step(fn, new_sig, new_pos, new_named)
        except TypeError as err:
            raise CurryBadArguments(func_name=_extract_name(fn), err=err.args[0]) from None

    return wraps(fn)(_curry_step_inner)


def curry(fn: Callable[..., R]) -> Callable[..., Union[Callable, R]]:
    """
        Currying decorator for a function with an arbitrary signature.
        :raises CurryBadFunctionError: passed function is not suitable
        :raises CurryBadArguments: error at the level of the arguments being passed
    """
    _panic_on_bad_curried(func=fn)

    def curried(*args, **kwargs) -> Union[Callable, R]:
        return _curry_step(fn, inspect.signature(fn), list(), dict())(*args, **kwargs)

    return wraps(fn)(curried)

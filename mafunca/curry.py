import inspect
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Union

from mafunca.common.exceptions import CurryBadFunctionError, CurryBadArguments
from mafunca.specials import is_impure, impure


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


def _wrap_and_check_impure(wrapper, fn):
    wrapper_new = wraps(fn)(wrapper)
    if is_impure(fn):
        wrapper_new = impure(wrapper_new)
    return wrapper_new


def curry2(fn: Callable[[A, B], R]) -> Callable[[A], Callable[[B], R]]:
    """
        Currying decorator for a function with two POSITIONAL arguments.
        If the original function is marked as impure,
        this property is only transferred to the last step before the actual call
    """
    def curry2_step1(arg1: A) -> Callable[[B], R]:
        def curry2_final(arg2: B) -> R:
            return fn(arg1, arg2)
        return _wrap_and_check_impure(curry2_final, fn)
    return curry2_step1


def curry3(fn: Callable[[A, B, C], R]) -> Callable[[A], Callable[[B], Callable[[C], R]]]:
    """
        Currying decorator for a function with three POSITIONAL arguments.
        If the original function is marked as impure,
        this property is only transferred to the last step before the actual call
    """
    def curry_step1(arg1: A) -> Callable[[B], Callable[[C], R]]:
        def curry3_step2(arg2: B) -> Callable[[C], R]:
            def curry3_final(arg3: C) -> R:
                return fn(arg1, arg2, arg3)
            return _wrap_and_check_impure(curry3_final, fn)
        return curry3_step2
    return curry_step1


def curry4(fn: Callable[[A, B, C, D], R]) -> Callable[[A], Callable[[B], Callable[[C], Callable[[D], R]]]]:
    """
        Currying decorator for a function with four POSITIONAL arguments.
        If the original function is marked as impure,
        this property is only transferred to the last step before the actual call
    """
    def curry4_step1(arg1: A) -> Callable[[B], Callable[[C], Callable[[D], R]]]:
        def curry4_step2(arg2: B) -> Callable[[C], Callable[[D], R]]:
            def curry4_step3(arg3: C) -> Callable[[D], R]:
                def curry4_final(arg4: D) -> R:
                    return fn(arg1, arg2, arg3, arg4)
                return _wrap_and_check_impure(curry4_final, fn)
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
    if not inspect.isfunction(func):
        raise CurryBadFunctionError(func_name=_extract_name(func), err="must be a callable")
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

    return _wrap_and_check_impure(_curry_step_inner, fn)


def curry(fn: Callable[..., R]) -> Callable[..., Union[Callable, R]]:
    """
        Currying decorator for a function with an arbitrary signature.
        Since any number of arguments can be passed at each step,
        the impure marking of the original function is set immediately.
        :raises CurryBadFunctionError: passed function is not suitable
        :raises CurryBadArguments: error at the level of the arguments being passed
    """
    _panic_on_bad_curried(func=fn)

    def curried(*args, **kwargs) -> Union[Callable, R]:
        return _curry_step(fn, inspect.signature(fn), list(), dict())(*args, **kwargs)

    return _wrap_and_check_impure(curried, fn)

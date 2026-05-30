import inspect
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Generic, Union

from mafunca.common.exceptions import CurryBadArguments
from mafunca.specials import is_impure, impure
from mafunca.specials import _get_impure_property  # noqa
import mafunca.common._panics as panics # noqa


__all__ = [
    'curry2',
    'curry3',
    'curry4',
    'curry',
    'Curry'
]


_IMPURE_PROP = _get_impure_property()


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
    def curry2_step1(arg1: A) -> Callable[[B], R]:
        def curry2_final(arg2: B) -> R:
            return fn(arg1, arg2)
        return _wrap_and_check_impure(curry2_final, fn)
    return curry2_step1


def curry3(fn: Callable[[A, B, C], R]) -> Callable[[A], Callable[[B], Callable[[C], R]]]:
    def curry_step1(arg1: A) -> Callable[[B], Callable[[C], R]]:
        def curry3_step2(arg2: B) -> Callable[[C], R]:
            def curry3_final(arg3: C) -> R:
                return fn(arg1, arg2, arg3)
            return _wrap_and_check_impure(curry3_final, fn)
        return curry3_step2
    return curry_step1


def curry4(fn: Callable[[A, B, C, D], R]) -> Callable[[A], Callable[[B], Callable[[C], Callable[[D], R]]]]:
    def curry4_step1(arg1: A) -> Callable[[B], Callable[[C], Callable[[D], R]]]:
        def curry4_step2(arg2: B) -> Callable[[C], Callable[[D], R]]:
            def curry4_step3(arg3: C) -> Callable[[D], R]:
                def curry4_final(arg4: D) -> R:
                    return fn(arg1, arg2, arg3, arg4)
                return _wrap_and_check_impure(curry4_final, fn)
            return curry4_step3
        return curry4_step2
    return curry4_step1


def _in_place_endpoints_filter(sig: inspect.Signature, bound_args: inspect.BoundArguments) -> inspect.BoundArguments:
    """Cleaning arguments of the *args and **kwargs type - they should not have default values applied to them"""
    for name, par in sig.parameters.items():
        if par.kind == inspect.Parameter.VAR_KEYWORD or par.kind == inspect.Parameter.VAR_POSITIONAL:
            bound_args.arguments.pop(name, None)
    return bound_args


def _apply(sig: inspect.Signature, *args, **kwargs) -> inspect.BoundArguments:
    """
        Applying arguments to a function signature.
        :raises TypeError: error of 'bind_partial' method.
    """
    bound_args = sig.bind_partial(*args, **kwargs)
    if len(args) == 0 and len(kwargs) == 0:
        bound_args.apply_defaults()
        _in_place_endpoints_filter(sig=sig, bound_args=bound_args)
    return bound_args


def _update_state(curry_obj: 'Curry', sig, pos, named) -> None:
    """Inner and dirty - update part of inner object state"""
    curry_obj._sig = sig  # noqa
    curry_obj._pos = pos  # noqa
    curry_obj._named = named  # noqa


class Curry(Generic[R]):
    __slots__ = ('_func', '_sig', '_pos', '_named', f'{_IMPURE_PROP}')

    def __init__(self, fn: Callable[..., R]):
        """:raises CurryBadFunctionError: passed function is not suitable"""
        panics.on_bad_curried(func=fn)
        self._func = fn
        self._sig = inspect.signature(fn)
        self._pos = []
        self._named = {}
        setattr(self, _IMPURE_PROP, is_impure(fn))

    @property
    def origin(self) -> Callable[..., R]:
        return self._func

    def __call__(self, *args, **kwargs) -> Union['Curry[R]', R]:
        """:raises CurryBadArguments: error at the level of the arguments being passed"""
        try:
            bound_args = _apply(self._sig, *args, **kwargs)
            new_params = [par for name, par in self._sig.parameters.items() if name not in bound_args.arguments]
            if len(new_params) == 0:
                return self._func(*self._pos, *bound_args.args, **self._named, **bound_args.kwargs)

            sig = inspect.Signature(parameters=new_params)
            new_curry = Curry(self._func)
            _update_state(
                new_curry,
                sig,
                [*self._pos, *bound_args.args],
                {**self._named, **bound_args.kwargs}
            )
            return new_curry
        except TypeError as err:
            raise CurryBadArguments(func_name=panics.extract_name(self._func), err=err.args[0]) from None

    def run_for_var(self) -> R:
        """
           Runs a function whose signature contains variable arguments without waiting for them to be passed.
           :raises CurryBadArguments: if not only variable arguments are left unset.
        """
        try:
            return self._func(*self._pos, **self._named)
        except TypeError as err:
            raise CurryBadArguments(func_name=panics.extract_name(self._func), err=err.args[0]) from None

    def __repr__(self):
        cls = type(self)
        name = cls.__qualname__
        module = cls.__module__
        args = [repr(self._func)]
        args.extend(repr(x) for x in self._pos)
        args.extend(f"{k}={v!r}" for (k, v) in self._named.items())
        return f"{module}.{name}({', '.join(args)}){self._sig}"


def curry(fn: Callable[..., R]) -> Curry[R]:
    """
       Decorator that turns a function into a curried version.
       :raises CurryBadFunctionError: passed function is not suitable
       :raises CurryBadArguments: error at the level of the arguments being passed
    """
    curried = Curry(fn)
    return curried

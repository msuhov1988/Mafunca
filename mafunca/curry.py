import inspect
from collections.abc import Callable, Awaitable
from typing import TypeVar, ParamSpec, Generic, Union, List, Dict

from mafunca.common.exceptions import CurryBadArguments
import mafunca.common.panics as panics


__all__ = ['curry', 'async_curry']


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


A = ParamSpec("A")
R = TypeVar("R")


class _Base:
    __slots__ = ('_func', '_sig', '_pos', '_named')

    def __init__(self, fn: Callable[[A], R]):
        self._func = fn
        self._sig = inspect.signature(fn)
        self._pos = []
        self._named = {}

    def _update_state(self, sig: inspect.Signature, pos: List, named: Dict):
        self._sig = sig
        self._pos = pos
        self._named = named

    @property
    def origin(self) -> Callable[[A], R]:
        return self._func

    def __repr__(self):
        cls = type(self)
        name = cls.__qualname__
        module = cls.__module__
        args = [repr(self._func)]
        args.extend(repr(x) for x in self._pos)
        args.extend(f"{k}={v!r}" for (k, v) in self._named.items())
        return f"{module}.{name}({', '.join(args)})"


class Curry(Generic[R], _Base):
    def __init__(self, fn: Callable[[A], R]):
        super().__init__(fn=fn)

    def __call__(self, *args: A.args, **kwargs: A.kwargs) -> Union['Curry[R]', R]:
        try:
            bound_args = _apply(self._sig, *args, **kwargs)
            new_params = [par for name, par in self._sig.parameters.items() if name not in bound_args.arguments]
            if len(new_params) == 0:
                return self._func(*self._pos, *bound_args.args, **self._named, **bound_args.kwargs)

            sig = inspect.Signature(parameters=new_params)
            new_curry = Curry(self._func)
            new_curry._update_state(sig, [*self._pos, *bound_args.args], {**self._named, **bound_args.kwargs})
            return new_curry
        except TypeError as err:
            raise CurryBadArguments(func_name=panics.extract_name(self._func), err=err.args[0]) from None

    def run_for_var(self) -> R:
        """
           Runs a function whose signature contains variable arguments without waiting for them to be passed.
           IMPORTANT: make sure that only variable arguments are left unset.
        """
        return self._func(*self._pos, **self._named)


class AsyncCurry(Generic[R], _Base):
    def __init__(self, fn: Callable[[A], Awaitable[R]]):
        super().__init__(fn=fn)

    async def __call__(self, *args: A.args, **kwargs: A.kwargs) -> Union['AsyncCurry[R]', R]:
        try:
            bound_args = _apply(self._sig, *args, **kwargs)
            new_params = [par for name, par in self._sig.parameters.items() if name not in bound_args.arguments]
            if len(new_params) == 0:
                return await self._func(*self._pos, *bound_args.args, **self._named, **bound_args.kwargs)

            sig = inspect.Signature(parameters=new_params)
            new_curry = AsyncCurry(self._func)
            new_curry._update_state(sig, [*self._pos, *bound_args.args], {**self._named, **bound_args.kwargs})
            return new_curry
        except TypeError as err:
            raise CurryBadArguments(func_name=panics.extract_name(self._func), err=err.args[0]) from None

    async def run_for_var(self) -> R:
        """
           Runs a function whose signature contains variable arguments without waiting for them to be passed.
           IMPORTANT: make sure that only variable arguments are left unset.
        """
        return await self._func(*self._pos, **self._named)


def curry(fn: Callable[[A], R]) -> Curry[R]:
    """
       Decorator that turns a SYNC ONLY function into a curried version.
       :raises CurryBadFunctionError: passed function is not suitable
       :raises CurryBadArguments: error at the level of the arguments being passed
    """
    panics.on_bad_curried(func=fn)
    panics.curry_on_coroutine(func=fn)
    curried = Curry(fn)
    curried.__doc__ = fn.__doc__
    return curried


def async_curry(fn: Callable[[A], Awaitable[R]]) -> AsyncCurry[R]:
    """
       Decorator that turns an ASYNC function into a curried version.
       :raises CurryBadFunctionError: passed function is not suitable
       :raises CurryBadArguments: error at the level of the arguments being passed
    """
    panics.on_bad_curried(func=fn)
    panics.curry_on_sync(func=fn)
    curried = AsyncCurry(fn)
    curried.__doc__ = fn.__doc__
    return curried

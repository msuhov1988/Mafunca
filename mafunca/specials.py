from dataclasses import dataclass
from collections.abc import Callable
from typing import TypeVar, ParamSpec, Generic


__all__ = ["impure", "is_impure"]


Params = ParamSpec('Params')
R = TypeVar("R")


@dataclass(frozen=True, slots=True, repr=True)
class _Impure(Generic[Params, R]):
    """
        A special callable object for wrapping functions with side effects.
        Using such objects in simple monads like Result causes an exception.
    """

    _func: Callable[Params, R]

    def __call__(self, *args: Params.args, **kwargs: Params.kwargs) -> R:
        return self._func(*args, **kwargs)

    def __repr__(self):
        cls = type(self)
        name = cls.__qualname__
        func = repr(self._func)
        return f"{name}({func})"


def impure(fn: Callable[Params, R]) -> _Impure[Params, R]:
    """
       Decorator - marks a function as impure by wrapping it in a special callable object
       to prevent its execution in a simple monads.
    """
    return _Impure(fn)


def is_impure(fn: Callable) -> bool:
    """Checking that the function was marked as impure"""
    return isinstance(fn, _Impure)

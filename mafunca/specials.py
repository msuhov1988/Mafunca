from collections.abc import Callable
from typing import TypeVar, ParamSpec
from mafunca.common.exceptions import ImpureMarkError


__all__ = ["impure", "is_impure"]


_IMPURE_PROP = '__impure__'


Args = ParamSpec('Args')
R = TypeVar('R')


def impure(fn: Callable[Args, R]) -> Callable[Args, R]:
    """
       Decorator - marks a function as impure(by adding a special attribute)
       to prevent its execution in a simple monads.
       :raises ImpureMarkError: can't mark it for any reason.
    """
    try:
        setattr(fn, _IMPURE_PROP, True)
    except Exception as err:
        raise ImpureMarkError(f"{fn}", str(err))
    return fn


def is_impure(fn: Callable) -> bool:
    """Checking that the function was marked as impure"""
    return bool(getattr(fn, _IMPURE_PROP, False))

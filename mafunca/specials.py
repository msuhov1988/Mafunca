from collections.abc import Callable
from typing import TypeVar, ParamSpec
from mafunca.common.exceptions import ImpureMarkError, MonadError


__all__ = ["impure", "is_impure"]


_IMPURE_PROP = '__mafunca_impure__'


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


def is_impure(fn) -> bool:
    """Checking that the function was marked as impure"""
    return bool(getattr(fn, _IMPURE_PROP, False))


def _get_impure_property() -> str:
    return _IMPURE_PROP


def _panic_on_impure(monad: str, method: str, *funcs: Callable) -> None:
    """:raises MonadError: if function is impure"""
    for fn in funcs:
        if is_impure(fn):
            raise MonadError(monad, method, f"impure function '{fn}' can not be used")

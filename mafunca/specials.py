from collections.abc import Callable
from mafunca.common.exceptions import ImpureMarkError


__all__ = ["impure", "is_impure"]


_IMPURE_PROP = '__impure__'


def impure(fn: Callable):
    """
       Decorator - marks a function as impure(by adding a special attribute)
       to prevent its execution in a simple monads.
       :raises ImpureMarkError: can't mark it for any reason.
    """
    try:
        setattr(fn, _IMPURE_PROP, True)
    except Exception as err:
        raise ImpureMarkError(fn.__name__, str(err))
    return fn


def is_impure(fn: Callable) -> bool:
    """Checking that the function was marked as impure"""
    return bool(getattr(fn, _IMPURE_PROP, False))

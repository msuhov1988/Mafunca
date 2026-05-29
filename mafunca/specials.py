from collections.abc import Callable


__all__ = ["impure", "is_impure"]


def impure(fn: Callable):
    """
       Decorator - marks a function as impure to prevent its execution in a simple monads.
    """
    fn.__impure__ = True
    return fn


def is_impure(fn: Callable) -> bool:
    """Checking that the function was marked as impure"""
    return bool(getattr(fn, "__impure__", False))

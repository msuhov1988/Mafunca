from dataclasses import dataclass
from collections.abc import Callable
from typing import TypeVar, Generic, TypeAlias, TypeGuard, Never


__all__ = [
    "Just",
    "Nothing",
    "Maybe",
    "just",
    "nothing",
    "is_just",
    "is_nothing",
    "from_null",
]


T_co = TypeVar("T_co", covariant=True)
T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True, slots=True, repr=True)
class Just(Generic[T_co]):
    """A container for non-nullable value"""
    value: T_co


@dataclass(frozen=True, slots=True, repr=True)
class Nothing:
    """A container representing the absence of a value"""
    pass


Maybe: TypeAlias = Just[T] | Nothing


def just(value: T) -> Maybe[T]:
    return Just(value)


def nothing() -> Maybe[Never]:
    return Nothing()


def is_just(maybe: Maybe[T]) -> TypeGuard[Just[T]]:
    return True if isinstance(maybe, Just) else False


def is_nothing(maybe: Maybe[T]) -> TypeGuard[Nothing]:
    return True if isinstance(maybe, Nothing) else False


def from_null(value: R, is_nullable: Callable[[R], bool] = lambda v: v is None) -> Maybe[R]:
    return Nothing() if is_nullable(value) else Just(value)

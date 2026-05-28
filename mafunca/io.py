from dataclasses import dataclass
from collections.abc import Callable
from typing import Generic, TypeVar, Any, cast

from mafunca.common.exceptions import MonadError


A = TypeVar("A")
B = TypeVar("B")


class IO(Generic[A]):
    def map(self, fn: Callable[[A], B]) -> 'IO[B]':
        return FlatMap(self, lambda a: Pure(fn(a)))

    def bind(self, fn: Callable[[A], 'IO[B]']) -> 'IO[B]':
        return FlatMap(self, fn)

    @staticmethod
    def of(value: A) -> 'IO[A]':
        return Pure(value)

    @staticmethod
    def effect(fn: Callable[[], A]) -> 'IO[A]':
        return Prime(fn)

    def run(self) -> A:
        current = self
        sequels = list()
        while True:
            if isinstance(current, FlatMap):
                sequels.append(current.cont)
                current = current.sub
            elif isinstance(current, Prime):
                current = Pure(current.effect())
            elif isinstance(current, Pure):
                if not sequels:
                    return cast(A, current.value)
                seq = sequels.pop()
                current = seq(current.value)
            else:
                raise MonadError(
                    self.__class__.__name__,
                    'run',
                    f"violation of the contract - unknown node {current}")


@dataclass(frozen=True, slots=True, repr=True)
class Pure(IO[A]):
    value: A


@dataclass(frozen=True, slots=True, repr=True)
class Prime(IO[A]):
    effect: Callable[[], A]


@dataclass(frozen=True, slots=True, repr=True)
class FlatMap(IO[B]):
    sub: IO[Any]
    cont: Callable[[Any], IO[B]]

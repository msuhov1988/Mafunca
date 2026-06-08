from dataclasses import dataclass

from collections.abc import Callable
from typing import Generic, TypeVar, Optional, Any


A = TypeVar("A")


@dataclass(frozen=True, slots=True, repr=True)
class Report(Generic[A]):
    last_successfully: Any
    exception: Optional[Exception]
    faulty: Optional[Callable]
    remainder: Optional[A]

    @property
    def completed_successfully(self) -> bool:
        """True if remainder is None, False otherwise"""
        return self.remainder is None

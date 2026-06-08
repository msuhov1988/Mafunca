from dataclasses import dataclass

from collections.abc import Callable
from typing import Generic, TypeVar, Optional


_LastSuccess = TypeVar("_LastSuccess")
_Remainder = TypeVar("_Remainder")


@dataclass(frozen=True, slots=True, repr=True)
class Report(Generic[_LastSuccess, _Remainder]):
    last_successfully: Optional[_LastSuccess]
    exception: Optional[Exception]
    faulty: Optional[Callable]
    remainder: Optional[_Remainder]

    @property
    def completed_successfully(self) -> bool:
        """True if exception is None, False otherwise"""
        return self.exception is None

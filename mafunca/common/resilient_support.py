from typing import TypeVar, Generic, NoReturn, Optional
from collections.abc import Callable


__all__ = ['Uncaught', 'Report']


Exc = TypeVar('Exc', bound=Exception)


class Uncaught(Generic[Exc]):
    """Special container for uncaught by user code exception"""

    __slots__ = ('_error',)

    def __init__(self, error: Exc):
        self._error = error

    @property
    def error(self) -> Exc:
        return self._error

    def throw(self) -> NoReturn:
        """:raises Exc: raises inner exception"""
        raise self._error

    def __repr__(self):
        return f'Uncaught({self._error.__class__})'


A = TypeVar('A')
B = TypeVar('B')


class Report(Generic[A, B]):
    """A container that contains the result, a shortened chain (optional) and a failure function (optional)"""

    __slots__ = ('_result', '_chain_from_failure', '_faulty', '_last_success')

    def __init__(self, result: A, chain_from_failure: B, faulty: Optional[Callable], last_success):
        self._result = result
        self._chain_from_failure = chain_from_failure
        self._faulty = faulty
        self._last_success = last_success

    @property
    def result(self) -> A:
        return self._result

    @property
    def chain_from_failure(self) -> B:
        return self._chain_from_failure

    @property
    def faulty(self) -> Optional[Callable]:
        return self._faulty

    @property
    def last_success(self):
        return self._last_success

    @property
    def is_ok(self) -> bool:
        return self._chain_from_failure is None

    def __repr__(self):
        result = f'result={self._result}'
        chain = f'chain_from_failure={self._chain_from_failure}'
        faulty = f'faulty={self._faulty}'
        last_success = f'last_success={self._last_success}'
        return f'Report({result}, {chain}, {faulty}, {last_success})'

from typing import TypeVar, Generic, NoReturn, Optional, List, Tuple
from collections.abc import Callable


__all__ = ['Uncaught', 'Report', 'ReportState', 'get_indexes_for_execution']


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
    """
        For resilient effects.
        A container that contains the result, a shortened chain (optional) and a failure function (optional).
    """

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

    @property
    def contains_an_uncaught(self) -> bool:
        return isinstance(self._result, Uncaught)

    def __repr__(self):
        result = f'result={self._result}'
        chain = f'chain_from_failure={self._chain_from_failure}'
        faulty = f'faulty={self._faulty}'
        last_success = f'last_success={self._last_success}'
        return f'Report({result}, {chain}, {faulty}, {last_success})'


R = TypeVar('R')
S = TypeVar('S')
RecoveredChain = TypeVar('RecoveredChain')


class ReportState(Generic[R, S, RecoveredChain]):
    """
        For resilient states.
        A container that contains the result, a shortened chain (optional) and a failure function (optional).
    """

    __slots__ = ('_result', '_state', '_chain_from_failure', '_faulty', '_last_success_result', '_last_clean_state')

    def __init__(
        self,
        result: R,
        state: S,
        chain_from_failure: RecoveredChain,
        faulty: Optional[Callable],
        last_success_result,
        last_clean_state: Optional[S],
    ):
        self._result = result
        self._state = state
        self._chain_from_failure = chain_from_failure
        self._faulty = faulty
        self._last_success_result = last_success_result
        self._last_clean_state = last_clean_state

    @property
    def result(self) -> R:
        return self._result

    @property
    def state(self) -> S:
        return self._state

    @property
    def chain_from_failure(self) -> RecoveredChain:
        return self._chain_from_failure

    @property
    def faulty(self) -> Optional[Callable]:
        return self._faulty

    @property
    def last_success_result(self):
        return self._last_success_result

    @property
    def last_clean_state(self) -> Optional[S]:
        return self._last_clean_state

    @property
    def is_ok(self) -> bool:
        return self._chain_from_failure is None

    @property
    def contains_an_uncaught(self) -> bool:
        return isinstance(self._result, Uncaught)

    def __repr__(self):
        result = f'result={self._result}'
        state = f'state={self._state}'
        chain = f'chain_from_failure={self._chain_from_failure}'
        faulty = f'faulty={self._faulty}'
        ls_result = f'last_success_result={self._last_success_result}'
        lc_state = f'last_success_state={self._last_clean_state}'
        return f'Report({result}, {state}, {chain}, {faulty}, {ls_result}, {lc_state})'


def get_indexes_for_execution(steps: Optional[int], inverted_cons: List) -> Tuple[int, int]:
    chain_length = len(inverted_cons) + 1  # +1 since prime always comes first, in addition to inverted_cons
    bounded_steps = chain_length if steps is None or steps > chain_length else steps
    bounded_steps_without_prime = bounded_steps - 1
    first_cont_index = len(inverted_cons) - 1  # inverted_cons is an inverted list, the last is the first
    last_cont_index = first_cont_index - bounded_steps_without_prime
    return first_cont_index, last_cont_index

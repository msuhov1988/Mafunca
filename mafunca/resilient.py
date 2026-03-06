from typing import TypeVar, Generic, overload, Union, Optional, List, Tuple
from collections.abc import Callable, Awaitable
import inspect
import asyncio

from mafunca.triple import Left, Nothing, TUtils
from mafunca.common.resilient_support import Uncaught, Report
from mafunca.common.exceptions import MonadError


__all__ = ['of', 'unit', 'ResilientPrime', 'ResilientCont', 'insist']


Exc = TypeVar('Exc', bound=Exception)
A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
L = TypeVar('L')


async def _maybe_await(obj: Union[Awaitable[A], A]) -> A:
    return await obj if inspect.isawaitable(obj) else obj


def _continuer(fn: Callable, bad_evaluator: Callable[..., bool]) -> Callable[..., Awaitable]:
    """
        Special async closure for continuation through the standard chain method.
        With short circuits on 'Uncaught' and custom 'bad' entities.
    """
    async def _continuer_inner(arg):
        if isinstance(arg, Uncaught) or bad_evaluator(arg):
            return arg
        return await _maybe_await(fn(arg))

    return _continuer_inner


def _catcher(fn: Callable) -> Callable[..., Awaitable]:
    """Special async closure for catching errors"""
    async def _catcher_inner(arg):
        if isinstance(arg, Uncaught):
            return await _maybe_await(fn(arg.error))
        return arg

    return _catcher_inner


def _ensurer(fn: Callable) -> Callable[..., Awaitable]:
    """An async closure simulating finally"""
    async def _ensurer_inner(arg):
        await _maybe_await(fn())
        return arg
    return _ensurer_inner


def _extract_from_closure(closure: Callable) -> Callable:
    """Extract origin function from closures like '_continuer' and etc"""
    cells = getattr(closure, "__closure__", ())
    if cells is None:
        return closure
    if len(cells) == 2:
        return cells[1].cell_contents
    elif len(cells) == 1:
        return cells[0].cell_contents
    else:
        return closure


class _Resilient(Generic[A]):
    __slots__ = ('_effect',)

    def __init__(self, effect: Callable[..., A]):
        self._effect = effect

    @overload
    def chain(self: '_Resilient[Uncaught[Exc]]', fn: Callable[[B], C]) -> 'ResilientCont[Uncaught[Exc]]': pass
    @overload
    def chain(self: '_Resilient[Left[L]]', fn: Callable[[B], C]) -> 'ResilientCont[Left[L]]': pass
    @overload
    def chain(self: '_Resilient[Nothing]', fn: Callable[[B], C]) -> 'ResilientCont[Nothing]': pass
    @overload
    def chain(self, fn: Callable[[A], '_Resilient[B]']) -> 'ResilientCont[B]': pass
    @overload
    def chain(self, fn: Callable[[A], Awaitable[B]]) -> 'ResilientCont[B]': pass
    @overload
    def chain(self, fn: Callable[[A], B]) -> 'ResilientCont[B]': pass

    def chain(self, fn):
        """Combines the logic of both 'map' and 'bind' in regular monads"""
        return ResilientCont(_continuer(fn, bad_evaluator=TUtils.is_bad), past=self)

    @overload
    def catch(self, fn: Callable[[Exc], '_Resilient[B]']) -> 'ResilientCont[Union[A, B]]': pass
    @overload
    def catch(self, fn: Callable[[Exc], Awaitable[B]]) -> 'ResilientCont[Union[A, B]]': pass
    @overload
    def catch(self, fn: Callable[[Exc], B]) -> 'ResilientCont[Union[A, B]]': pass

    def catch(self, fn):
        """
            Handles errors(Exception heirs) that occurred earlier in the chain.
        """
        return ResilientCont(_catcher(fn), past=self)

    def ensure(self, fn: Callable[[], Union[Awaitable[None], None]]) -> 'ResilientCont[A]':
        """
            Guaranteed to execute the function-parameter, similar to try finally.
            :raises MonadError: panics on coroutine function
        """
        return ResilientCont(_ensurer(fn), past=self)


async def _execute(value: A, fn: Callable):
    """
        Execute function from chain with catching errors.
        MonadError is not suppressed.
    """
    try:
        result = await fn(value)
        if isinstance(result, (ResilientPrime, ResilientCont)):
            report = await result.run()   # do not restore internal chains
            result = report.result
        return result
    except Exception as exc:
        if isinstance(exc, MonadError):
            raise exc
        return Uncaught(exc)


def _unwind(persist: 'ResilientCont') -> Tuple['ResilientPrime', List[Callable]]:
    """Unwinding the chain to the first effect"""
    current, effects = persist, []
    while isinstance(current, ResilientCont):
        effects.append(current.effect)
        current = current.past
    if isinstance(current, ResilientPrime):
        return current, effects
    raise MonadError(
        monad='Resilient',
        method='chain starter method',
        message="Violation of the usage contract - the first element in the chain must be a 'ResilientPrime' entity"
    )


_Sub = TypeVar('_Sub', bound=_Resilient)


class ResilientPrime(_Resilient[A]):
    """Use only for typing purposes. To create monads, use the 'of' and 'unit' functions and chained methods"""

    def __init__(self, effect: Callable[[], A]):
        super().__init__(effect)

    @property
    def effect(self) -> Callable[[], A]:
        return self._effect

    async def _launch(self, rebuild: bool = False) -> Report[Union[A, Uncaught[Exc]], Optional['ResilientPrime']]:
        result = await _execute(self._effect(), _maybe_await)
        restored, faulty = None, None
        if rebuild and (isinstance(result, Uncaught) or TUtils.is_bad(result)):
            restored, faulty = ResilientPrime(self._effect), self._effect
        return Report(result, chain_from_failure=restored, faulty=faulty)

    async def run(
            self,
            rebuild: bool = False,
            delay: Optional[Union[int, float]] = None
    ) -> Report[Union[A, Uncaught], Optional['ResilientPrime']]:
        """
            Async - starts the chain.
            :raises TimeoutError: delay is not None and the waiting time has been exceeded.
        """
        if delay is None:
            return await self._launch(rebuild=rebuild)
        else:
            async with asyncio.timeout(delay=delay):
                return await self._launch(rebuild=rebuild)

    def to_task(self, rebuild: bool = False) -> asyncio.Task:
        """Wrap the chain starter method into a Task"""
        return asyncio.create_task(self._launch(rebuild=rebuild))


def _make_effect(val: A) -> Callable[[], A]:
    """To prevent lambda from updating the reference when it is reassigned  in a loop"""
    return lambda: val


class ResilientCont(_Resilient[B]):
    """Use only for typing purposes. To create monads, use the 'of' and 'unit' functions and chained methods"""

    __slots__ = ('_past',)

    def __init__(self, effect: Callable[[A], B], past: _Sub):
        super().__init__(effect)
        self._past = past

    @property
    def effect(self) -> Callable[[A], B]:
        return self._effect

    @property
    def past(self) -> _Sub:
        return self._past

    async def _launch(self, rebuild: bool = False) -> Report[Union[B, Uncaught[Exc]], Optional['ResilientCont']]:
        """
            Starts the chain
            :raises MonadError: violations of monadic contracts
        """
        persist_prime, cons = _unwind(persist=self)
        report_prime = await persist_prime.run(rebuild=rebuild)
        result, restored, faulty = report_prime.result, report_prime.chain_from_failure, report_prime.faulty

        for i in range(len(cons) - 1, -1, -1):
            result_new = await _execute(result, cons[i])
            if rebuild:
                if isinstance(result_new, Uncaught) or TUtils.is_bad(result_new):
                    if restored is None:
                        prime = ResilientPrime(_make_effect(result))
                        restored, faulty = ResilientCont(cons[i], past=prime), _extract_from_closure(cons[i])
                    else:
                        restored = ResilientCont(cons[i], past=restored)
                else:
                    restored, faulty = None, None
            result = result_new

        if isinstance(result, Uncaught) or TUtils.is_bad(result):
            return Report(result, chain_from_failure=restored, faulty=faulty)
        else:
            return Report(result, chain_from_failure=None, faulty=None)

    async def run(
            self,
            rebuild: bool = False,
            delay: Optional[Union[int, float]] = None
    ) -> Report[Union[A, Uncaught], Optional['ResilientCont']]:
        """
            Async - starts the chain.
            :raises TimeoutError: delay is not None and the waiting time has been exceeded.
        """
        if delay is None:
            return await self._launch(rebuild=rebuild)
        else:
            async with asyncio.timeout(delay=delay):
                return await self._launch(rebuild=rebuild)

    def to_task(self, rebuild: bool = False) -> asyncio.Task:
        """Wrap the chain starter method into a Task"""
        return asyncio.create_task(self._launch(rebuild=rebuild))


def of(value: A) -> ResilientPrime[A]:
    """
        Lazy monad for resilient async effects.
        Can accept both async and sync functions.
        Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
        Automatically catches errors and wraps them in an 'Uncaught' object.
        Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return ResilientPrime(lambda: value)


def unit(fn: Callable[[], A]) -> ResilientPrime[A]:
    """
        Lazy monad for resilient async effects.
        Can accept both async and sync functions.
        Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
        Automatically catches errors and wraps them in an 'Uncaught' object.
        Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return ResilientPrime(fn)


async def insist(
        resilient: Union[ResilientPrime[A], ResilientCont[A]],
        attempts: int = 1,
        delay_for_attempt: Union[int, float] = None,
        pause_between: Union[int, float] = 0
) -> Report[Union[A, Uncaught[Exc]], Optional['ResilientCont']]:
    """
        Makes 'attempts' with 'delay_for_attempt' to execute a 'resilient' chain
        with 'pause_between' intervals between them
    """
    chain, report = resilient, Report(None, resilient, None)
    for _ in range(attempts):
        if delay_for_attempt is None:
            report = await chain.run(rebuild=True)
        else:
            try:
                async with asyncio.timeout(delay=delay_for_attempt):
                    return await chain.run(rebuild=True)
            except TimeoutError:
                await asyncio.sleep(pause_between)
                continue

        if not report.is_ok:
            chain = report.chain_from_failure
            await asyncio.sleep(pause_between)
    return report

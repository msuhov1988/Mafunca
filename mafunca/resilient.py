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


_ORIGIN_LINK = "__mafunca_resilient_origin__"


def _continuer(fn: Callable, bad_evaluator: Callable[..., bool]) -> Callable[..., Awaitable]:
    """
        Special async closure for continuation through the standard chain method.
        With short circuits on 'Uncaught' and custom 'bad' entities.
    """
    async def _continuer_inner(arg):
        if isinstance(arg, Uncaught) or bad_evaluator(arg):
            return arg
        return await _maybe_await(fn(arg))

    setattr(_continuer_inner, _ORIGIN_LINK, fn)
    return _continuer_inner


def _catcher(fn: Callable) -> Callable[..., Awaitable]:
    """Special async closure for catching errors"""
    async def _catcher_inner(arg):
        if isinstance(arg, Uncaught):
            return await _maybe_await(fn(arg.error))
        return arg

    setattr(_catcher_inner, _ORIGIN_LINK, fn)
    return _catcher_inner


def _ensurer(fn: Callable) -> Callable[..., Awaitable]:
    """An async closure simulating finally"""
    async def _ensurer_inner(arg):
        await _maybe_await(fn())
        return arg

    setattr(_ensurer_inner, _ORIGIN_LINK, fn)
    return _ensurer_inner


def _extract_from_closure(closure: Callable) -> Callable:
    """Extract origin function from closures like '_continuer' and etc"""
    origin = getattr(closure, _ORIGIN_LINK, None)
    if origin is None:
        return closure
    return origin


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
        """Handles errors(Exception heirs) that occurred earlier in the chain."""
        return ResilientCont(_catcher(fn), past=self)

    def ensure(self, fn: Callable[[], Union[Awaitable[None], None]]) -> 'ResilientCont[A]':
        """Guaranteed to execute the function-parameter, similar to try finally."""
        return ResilientCont(_ensurer(fn), past=self)


class ResilientPrime(_Resilient[A]):
    """Use only for typing purposes. To create monads, use the 'of' and 'unit' functions and chained methods"""

    def __init__(self, effect: Callable[[], A]):
        super().__init__(effect)

    @property
    def effect(self) -> Callable[[], A]:
        return self._effect

    async def _launch(self, rebuild: bool = False) -> Report[Union[A, Uncaught[Exc]], Optional['ResilientPrime']]:
        try:
            result = await _maybe_await(self._effect())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            result = Uncaught(exc)
        if rebuild and (isinstance(result, Uncaught) or TUtils.is_bad(result)):
            return Report(result, ResilientPrime(self._effect), self._effect, None)
        return Report(result, chain_from_failure=None, faulty=None, last_success=None)

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


async def _execute(value: A, fn: Callable):
    """
        Execute function from chain with catching errors.
        MonadError is not suppressed.
    """
    try:
        return await fn(value)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if isinstance(exc, MonadError):
            raise exc
        return Uncaught(exc)


def _make_effect(val: A) -> Callable[[], A]:
    """To prevent lambda from updating the reference when it is reassigned  in a loop"""
    return lambda: val


_Sub = TypeVar('_Sub', bound=_Resilient)


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
        result, restored = report_prime.result, report_prime.chain_from_failure
        faulty, last_success = report_prime.faulty, report_prime.last_success

        for i in range(len(cons) - 1, -1, -1):
            result_new, restored_new = await _execute(result, cons[i]), None
            faulty_new, last_success_new = None, None
            if isinstance(result_new, (ResilientPrime, ResilientCont)):
                rpt = await result_new.run(rebuild=rebuild)
                result_new, restored_new = rpt.result, rpt.chain_from_failure
                faulty_new, last_success_new = rpt.faulty, rpt.last_success

            if rebuild:
                if restored_new:
                    # if we're in this branch, it's the first failure!
                    restored, faulty, last_success = restored_new, faulty_new, last_success_new
                elif isinstance(result_new, Uncaught) or TUtils.is_bad(result_new):
                    if restored is None:
                        prime = ResilientPrime(_make_effect(result))
                        restored, faulty = ResilientCont(cons[i], past=prime), _extract_from_closure(cons[i])
                        last_success = result
                    else:
                        restored = ResilientCont(cons[i], past=restored)
                else:
                    restored, faulty, last_success = None, None, result_new
            result = result_new

        return Report(result, chain_from_failure=restored, faulty=faulty, last_success=last_success)

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
    chain, report = resilient, Report(None, resilient, None, None)

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
            continue
        return report

    return report

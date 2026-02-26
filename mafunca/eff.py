from typing import TypeVar, Generic, overload, Union, Optional
from collections.abc import Callable, Awaitable
import inspect
import asyncio

from mafunca.triple import Left, Nothing, TUtils
from mafunca.exceptions import MonadError


__all__ = ['Eff']


A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')

L = TypeVar('L')
Exc = TypeVar('Exc', bound=Exception)
T = TypeVar('T')


def _panic_on_coroutine(fn: Callable, monad_name: str, method: str):
    if inspect.iscoroutinefunction(fn):
        raise MonadError(monad_name, method, f"function '{fn.__name__}' - async function can not be used")


def _panic_on_sync(fn: Callable, monad_name: str, method: str):
    if not inspect.iscoroutinefunction(fn):
        raise MonadError(monad_name, method, f"function '{fn.__name__}' - sync function can not be used")


def _panic_on_monadic_result(result, fn: Callable, monad, method: str):
    if isinstance(result, monad):
        monad_name = monad.__name__
        raise MonadError(
            monad_name,
            method,
            f"return value {result} of applying function '{fn.__name__}' - must not be '{monad_name}' entity"
        )


def _panic_on_other_result(result, fn: Callable, monad, method: str):
    if not isinstance(result, monad):
        monad_name = monad.__name__
        raise MonadError(
            monad_name,
            method,
            f"return value {result} of applying function '{fn.__name__}' must be '{monad_name}' entity"
        )


async def _maybe_await(obj: Union[Awaitable[T], T]) -> T:
    return await obj if inspect.isawaitable(obj) else obj


class Eff(Generic[A]):
    """Lazy monad for async effects.
       It can work with bad 'Triple' entities using the short-circuit principle.
       Can work with both synchronous and asynchronous functions.
    """

    __slots__ = ["effect"]

    def __init__(self, effect: Callable[[], A]):
        self.effect = effect

    @overload
    def map(self: 'Eff[Left[L]]', fn: Callable[[B], C]) -> 'Eff[Left[L]]': pass
    @overload
    def map(self: 'Eff[Nothing]', fn: Callable[[B], C]) -> 'Eff[Nothing]': pass
    @overload
    def map(self, fn: Callable[[A], Awaitable[B]]) -> 'Eff[B]': pass
    @overload
    def map(self, fn: Callable[[A], B]) -> 'Eff[B]': pass

    def map(self, fn):
        """
           Applies a function that returns a non-Eff entity.
           It can accept both async and sync functions. Async functions are awaited.
           :raises MonadError: violation of the contract
        """

        async def new_effect():
            previous = await _maybe_await(self.effect())
            if TUtils.is_bad(previous):
                return previous
            current = await _maybe_await(fn(previous))
            _panic_on_monadic_result(current, fn=fn, monad=self.__class__, method='map')
            return current
        return Eff(new_effect)

    @overload
    def map_to_thread(self: 'Eff[Left[L]]', fn: Callable[[B], C]) -> 'Eff[Left[L]]': pass
    @overload
    def map_to_thread(self: 'Eff[Nothing]', fn: Callable[[B], C]) -> 'Eff[Nothing]': pass
    @overload
    def map_to_thread(self, fn: Callable[[A], B]) -> 'Eff[B]': pass

    def map_to_thread(self, fn):
        """
           Applies a SYNC ONLY function that returns a non-Eff entity.
           Executes it in a separate thread.
           :raises MonadError: violation of the contract
        """
        _panic_on_coroutine(fn, monad_name=self.__class__.__name__, method='map_to_thread')

        async def new_effect():
            previous = await _maybe_await(self.effect())
            if TUtils.is_bad(previous):
                return previous
            current = await asyncio.to_thread(fn, previous)
            _panic_on_monadic_result(current, fn=fn, monad=self.__class__, method='map_to_thread')
            return current

        return Eff(new_effect)

    @overload
    def bind(self: 'Eff[Left[L]]', fn: Callable[[B], C]) -> 'Eff[Left[L]]': pass
    @overload
    def bind(self: 'Eff[Nothing]', fn: Callable[[B], C]) -> 'Eff[Nothing]': pass
    @overload
    def bind(self, fn: Callable[[A], Awaitable['Eff[B]']]) -> 'Eff[B]': pass
    @overload
    def bind(self, fn: Callable[[A], 'Eff[B]']) -> 'Eff[B]': pass

    def bind(self, fn):
        """
           Applies a function that returns an Eff entity.
           It can accept both async and sync functions. Async functions are awaited.
           :raises MonadError: violation of the contract
        """

        async def new_effect():
            previous = await _maybe_await(self.effect())
            if TUtils.is_bad(previous):
                return previous
            current_effect = await _maybe_await(fn(previous))
            _panic_on_other_result(current_effect, fn=fn, monad=self.__class__, method='bind')
            current = await _maybe_await(current_effect.effect())
            return current
        return Eff(new_effect)

    @overload
    def bind_to_thread(self: 'Eff[Left[L]]', fn: Callable[[B], C]) -> 'Eff[Left[L]]': pass
    @overload
    def bind_to_thread(self: 'Eff[Nothing]', fn: Callable[[B], C]) -> 'Eff[Nothing]': pass
    @overload
    def bind_to_thread(self, fn: Callable[[A], 'Eff[B]']) -> 'Eff[B]': pass

    def bind_to_thread(self, fn):
        """
           Applies a SYNC ONLY function that returns an Eff entity.
           Executes it in a separate thread - ONLY an external function that returns AsyncIO.
           :raises MonadError: violation of the contract
        """
        _panic_on_coroutine(fn, monad_name=self.__class__.__name__, method='bind_to_thread')

        async def new_effect():
            previous = await _maybe_await(self.effect())
            if TUtils.is_bad(previous):
                return previous
            current_effect = await asyncio.to_thread(fn, previous)
            _panic_on_other_result(current_effect, fn=fn, monad=self.__class__, method='bind_to_thread')
            current = await _maybe_await(current_effect.effect())
            return current

        return Eff(new_effect)

    @overload
    def catch(self, fn: Callable[[Exc], Awaitable['Eff[B]']]) -> 'Eff[B]': pass
    @overload
    def catch(self, fn: Callable[[Exc], 'Eff[B]']) -> 'Eff[B]': pass
    @overload
    def catch(self, fn: Callable[[Exc], Awaitable[B]]) -> 'Eff[B]': pass
    @overload
    def catch(self, fn: Callable[[Exc], B]) -> 'Eff[B]': pass

    def catch(self, fn):
        """
           Catch errors(Exception heirs) in all deeper nested functions.
           It can return both Eff and non-Eff entities.
           It can accept both async and sync functions. Async functions are awaited.
           MonadError is not suppressed.
        """

        async def new_effect():
            try:
                return await _maybe_await(self.effect())
            except Exception as err:
                if isinstance(err, (MonadError, KeyboardInterrupt)):
                    raise err
                current = await _maybe_await(fn(err))
                if isinstance(current, self.__class__):
                    return await _maybe_await(current.effect())
                return current
        return Eff(new_effect)

    def ensure(self, fn: Callable[[], Union[Awaitable[None], None]]) -> 'Eff[A]':
        """Guaranteed to execute the function-parameter, similar to try finally.
           It can accept both async and sync functions. Async functions are awaited.
        """

        async def new_effect():
            try:
                return await _maybe_await(self.effect())
            finally:
                await _maybe_await(fn())
        return Eff(new_effect)

    def to_task(self) -> asyncio.Task:
        """Wrap the inner effect into a Task. Inner effect must be a coroutine function.
           :raises MonadError: inner effect is a sync function
        """
        _panic_on_sync(self.effect, monad_name=self.__class__.__name__, method='to_task')
        return asyncio.create_task(self.effect())

    async def run(self, delay: Optional[Union[int, float]] = None) -> A:
        """
           Async - starts the chain.
           :raises TimeoutError: delay is not None and the waiting time has been exceeded.
        """
        if delay is None:
            return await _maybe_await(self.effect())
        else:
            async with asyncio.timeout(delay=delay):
                return await _maybe_await(self.effect())

    @classmethod
    def of(cls, value: A) -> 'Eff[A]':
        """Wraps a non-Eff value in the container. No inspections here."""
        return Eff(lambda: value)

    def __repr__(self):
        return f"Eff({self.effect})"

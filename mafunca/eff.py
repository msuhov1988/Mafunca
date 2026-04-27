from typing import TypeVar, TypeAlias, Generic, Union, Optional
from collections.abc import Callable, Awaitable
import inspect
import asyncio

from mafunca.triple import Left, Nothing, TUtils
from mafunca.common.exceptions import MonadError
import mafunca.common._panics as panics # noqa


__all__ = ['Eff', 'DefaultBad']


_Exception = TypeVar('_Exception', bound=Exception)
_Ok = TypeVar('_Ok')
_Result = TypeVar('_Result')
_AwaitableOk = Union[Awaitable[_Ok], _Ok]
_AwaitableResult = Union[Awaitable[_Result], _Result]


DefaultBad = Union[Left, Nothing]
_Bad = TypeVar('_Bad', bound=DefaultBad)
_NewBad = TypeVar('_NewBad', bound=DefaultBad)
_AwaitableBad = Union[Awaitable[_Bad], _Bad]
_AwaitableNewBad = Union[Awaitable[_NewBad], _NewBad]

_T = TypeVar('_T')


async def _maybe_await(obj: Union[Awaitable[_T], _T]) -> _T:
    return await obj if inspect.isawaitable(obj) else obj


_Effect: TypeAlias = Callable[[], Union[_Ok, _Bad, Awaitable[_Ok], Awaitable[_Bad]]]
_AwaitableSelf: TypeAlias = Union[Awaitable['Eff[_Result, _NewBad]'], 'Eff[_Result, _NewBad]']


class Eff(Generic[_Ok, _Bad]):
    """Lazy monad for async effects.
       It can work with bad 'Triple' entities using the short-circuit principle.
       Can work with both synchronous and asynchronous functions.
    """

    __slots__ = ["_effect"]

    def __init__(self, effect: _Effect):
        self._effect = effect

    @property
    def effect(self) -> _Effect:
        return self._effect

    def map(
        self,
        fn: Callable[[_Ok], Union[_AwaitableResult, _AwaitableNewBad]]
    ) -> 'Eff[_Result, Union[_Bad, _NewBad]]':
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
            panics.on_monadic_result(current, fn=fn, monad=self.__class__, method='map')
            return current
        return Eff(new_effect)

    def map_to_thread(self, fn: Callable[[_Ok], Union[_Result, _NewBad]]) -> 'Eff[_Result, Union[_Bad, _NewBad]]':
        """
           Applies a SYNC ONLY function that returns a non-Eff entity.
           Executes it in a separate thread.
           :raises MonadError: violation of the contract
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='map_to_thread')

        async def new_effect():
            previous = await _maybe_await(self.effect())
            if TUtils.is_bad(previous):
                return previous
            current = await asyncio.to_thread(fn, previous)
            panics.on_monadic_result(current, fn=fn, monad=self.__class__, method='map_to_thread')
            return current

        return Eff(new_effect)

    def bind(self, fn: Callable[[_Ok], _AwaitableSelf]) -> 'Eff[_Result, Union[_Bad, _NewBad]]':
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
            panics.on_another_instance(current_effect, fn=fn, monad=self.__class__, method='bind')
            current = await _maybe_await(current_effect.effect())
            return current
        return Eff(new_effect)

    def bind_to_thread(self, fn: Callable[[_Ok], 'Eff[_Result, _NewBad]']) -> 'Eff[_Result, Union[_Bad, _NewBad]]':
        """
           Applies a SYNC ONLY function that returns an Eff entity.
           Executes it in a separate thread - ONLY inner function inside Eff.
           :raises MonadError: violation of the contract
        """

        async def new_effect():
            previous = await _maybe_await(self.effect())
            if TUtils.is_bad(previous):
                return previous
            current_effect = await _maybe_await(fn(previous))
            panics.on_another_instance(current_effect, fn=fn, monad=self.__class__, method='bind_to_thread')
            panics.on_coroutine(current_effect.effect, monad_name=self.__class__.__name__, method='bind_to_thread')
            current = await asyncio.to_thread(current_effect.effect)
            return current

        return Eff(new_effect)

    def catch(
        self,
        fn: Callable[[_Exception], Union[_AwaitableSelf, _AwaitableResult, _AwaitableNewBad]]
    ) -> 'Eff[_Result, Union[_Bad, _NewBad]]':
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
                if isinstance(err, MonadError):
                    raise err
                current = await _maybe_await(fn(err))
                if isinstance(current, self.__class__):
                    return await _maybe_await(current.effect())
                return current
        return Eff(new_effect)

    def ensure(self, fn: Callable[[], Union[Awaitable[None], None]]) -> 'Eff[_Ok, _Bad]':
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
        """Wraps the inner effect into a Task. Inner effect must be a coroutine function.
           :raises MonadError: inner effect is a sync function
        """
        panics.on_sync(self.effect, monad_name=self.__class__.__name__, method='to_task')
        return asyncio.create_task(self.effect())

    async def run(self, delay: Optional[Union[int, float]] = None) -> Union[_Ok, _Bad]:
        """
           Async - starts the chain.
           :raises TimeoutError: delay is not None and the waiting time has been exceeded.
        """
        if delay is None:
            return await _maybe_await(self.effect())
        else:
            async with asyncio.timeout(delay=delay):
                return await _maybe_await(self.effect())

    @staticmethod
    def of(value: Union[_Result, _NewBad]) -> 'Eff[_Result, _NewBad]':
        """Wraps a non-Eff value in the container. No inspections here."""
        return Eff(lambda: value)

    def __repr__(self):
        return f"Eff({self.effect})"

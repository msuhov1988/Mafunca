from typing import TypeVar, Generic, overload
from collections.abc import Callable

from mafunca.triple import Left, Nothing, TUtils
from mafunca.common.exceptions import MonadError
import mafunca.common.panics as panics


__all__ = ['EffSync']


A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')

L = TypeVar('L')
Exc = TypeVar('Exc', bound=Exception)


class EffSync(Generic[A]):
    """Lazy monad for sync effects.
       It can work with bad 'Triple' entities using the short-circuit principle
    """

    __slots__ = ["effect"]

    def __init__(self, effect: Callable[[], A]):
        panics.on_coroutine(effect, monad_name=self.__class__.__name__, method='__init__')
        self.effect = effect

    @overload
    def map(self: 'EffSync[Left[L]]', fn: Callable[[B], C]) -> 'EffSync[Left[L]]': pass
    @overload
    def map(self: 'EffSync[Nothing]', fn: Callable[[B], C]) -> 'EffSync[Nothing]': pass
    @overload
    def map(self, fn: Callable[[A], B]) -> 'EffSync[B]': pass

    def map(self, fn):
        """
           Applies a sync function that returns a non-EffSync entity.
           :raises MonadError: violation of the contract
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='map')

        def new_effect():
            previous = self.effect()
            if TUtils.is_bad(previous):
                return previous
            current = fn(previous)
            panics.on_monadic_result(current, fn=fn, monad=self.__class__, method='map')
            return current
        return EffSync(new_effect)

    @overload
    def bind(self: 'EffSync[Left[L]]', fn: Callable[[B], 'EffSync[C]']) -> 'EffSync[Left[L]]': pass
    @overload
    def bind(self: 'EffSync[Nothing]', fn: Callable[[B], 'EffSync[C]']) -> 'EffSync[Nothing]': pass
    @overload
    def bind(self, fn: Callable[[A], 'EffSync[B]']) -> 'EffSync[B]': pass

    def bind(self, fn):
        """
           Applies a sync function that returns an EffSync entity.
           :raises MonadError: violation of the contract
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='bind')

        def new_effect():
            previous = self.effect()
            if TUtils.is_bad(previous):
                return previous
            current_effect = fn(previous)
            panics.on_another_instance(current_effect, fn=fn, monad=self.__class__, method='bind')
            current = current_effect.effect()
            return current
        return EffSync(new_effect)

    @overload
    def catch(self, fn: Callable[[Exc], 'EffSync[B]']) -> 'EffSync[B]': pass
    @overload
    def catch(self, fn: Callable[[Exc], B]) -> 'EffSync[B]': pass

    def catch(self, fn):
        """
           Catch errors(Exception heirs) in all deeper nested functions.
           It can return both EffSync and non-EffSync entities.
           MonadError is not suppressed.
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='catch')

        def new_effect():
            try:
                return self.effect()
            except Exception as err:
                if isinstance(err, (MonadError, KeyboardInterrupt)):
                    raise err
                current = fn(err)
                if isinstance(current, self.__class__):
                    return current.effect()
                return current
        return EffSync(new_effect)

    def ensure(self, fn: Callable[[], None]) -> 'EffSync[A]':
        """Guaranteed to execute the function-parameter, similar to try finally"""
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='ensure')

        def new_effect():
            try:
                return self.effect()
            finally:
                fn()
        return EffSync(new_effect)

    def run(self) -> A:
        """Starts the chain"""
        return self.effect()

    @classmethod
    def of(cls, value: A) -> 'EffSync[A]':
        """Wraps a non-EffSync value in the container. No inspections here."""
        return EffSync(lambda: value)

    def __repr__(self):
        return f"EffSync({self.effect})"

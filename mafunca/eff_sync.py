from typing import TypeVar, Generic, Union
from collections.abc import Callable

from mafunca.triple import Left, Nothing, TUtils
from mafunca.common.exceptions import MonadError
import mafunca.common._panics as panics # noqa


__all__ = ['EffSync', 'DefaultBad']


_Exception = TypeVar('_Exception', bound=Exception)
_Ok = TypeVar('_Ok')
_Result = TypeVar('_Result')

DefaultBad = Union[Left, Nothing]
_Bad = TypeVar('_Bad', bound=DefaultBad)
_NewBad = TypeVar('_NewBad', bound=DefaultBad)


class EffSync(Generic[_Ok, _Bad]):
    """Lazy monad for sync effects.
       It can work with bad 'Triple' entities using the short-circuit principle
    """

    __slots__ = ["_effect"]

    def __init__(self, effect: Callable[[], Union[_Ok, _Bad]]):
        panics.on_coroutine(effect, monad_name=self.__class__.__name__, method='__init__')
        self._effect = effect

    @property
    def effect(self) -> Callable[[], Union[_Ok, _Bad]]:
        return self._effect

    def map(self, fn: Callable[[_Ok], Union[_Result, _NewBad]]) -> 'EffSync[_Result, Union[_Bad, _NewBad]]':
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

    def bind(self, fn: Callable[[_Ok], 'EffSync[_Result, _NewBad]']) -> 'EffSync[_Result, Union[_Bad, _NewBad]]':
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

    def catch(
        self,
        fn: Callable[[_Exception], Union['EffSync[_Result, _NewBad]', _Result, _NewBad]]
    ) -> 'EffSync[_Result, Union[_Bad, _NewBad]]':
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
                if isinstance(err, MonadError):
                    raise err
                current = fn(err)
                if isinstance(current, self.__class__):
                    return current.effect()
                return current
        return EffSync(new_effect)

    def ensure(self, fn: Callable[[], None]) -> 'EffSync[_Ok, _Bad]':
        """Guaranteed to execute the function-parameter, similar to try finally"""
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='ensure')

        def new_effect():
            try:
                return self.effect()
            finally:
                fn()
        return EffSync(new_effect)

    def run(self) -> Union[_Ok, _Bad]:
        """Starts the chain"""
        return self.effect()

    @staticmethod
    def of(value: Union[_Result, _NewBad]) -> 'EffSync[_Result, _NewBad]':
        """Wraps a non-EffSync value in the container. No inspections here."""
        return EffSync(lambda: value)

    def __repr__(self):
        return f"EffSync({self.effect})"

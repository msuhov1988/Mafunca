from abc import ABC, abstractmethod
from typing import TypeVar, ParamSpec, Generic, Union, overload
from collections.abc import Callable
import inspect
from functools import wraps

from mafunca.exceptions import ImpureMarkError, MonadError


__all__ = [
    'impure',
    'is_impure',
    'Right',
    'Left',
    'Nothing',
    'TUtils',
]


_IMPURE_PROP = 'mafunca_impure'


def impure(fn: Callable):
    """
       Decorator - marks a function as impure(by adding a special attribute)
       to prevent its execution in a triple monad.
       :raises ImpureMarkError: can't mark it for any reason.
    """
    try:
        setattr(fn, _IMPURE_PROP, True)
    except Exception as err:
        raise ImpureMarkError(fn.__name__, str(err))
    return fn


def is_impure(fn: Callable) -> bool:
    """Checking that the function was marked as impure"""
    return getattr(fn, _IMPURE_PROP, False)


R = TypeVar("R")
L = TypeVar("L")

V = TypeVar("V")
W = TypeVar("W")
X = TypeVar("X")


class Triple(ABC):
    """Abstract class for simple monad over the value that is available here and now"""
    @property
    @abstractmethod
    def is_right(self) -> bool:
        pass

    @property
    @abstractmethod
    def is_nothing(self) -> bool:
        pass

    @abstractmethod
    def map(self, fn: Callable[[R], V]):
        pass

    @abstractmethod
    def bind(self, fn: Callable[[R], 'Triple']):
        pass

    @abstractmethod
    def recover_from_left(self, fn: Callable[[L], V]):
        pass

    @abstractmethod
    def recover_from_nothing(self, fn: Callable[[], V]):
        pass

    @abstractmethod
    def unfold(self, *, right: Callable[[R], V], left: Callable[[L], W], nothing: Callable[[], X]):
        pass

    @abstractmethod
    def ap(self, wrapped_val: 'Triple'):
        pass

    @abstractmethod
    def get_or_else(self, alter: V):
        pass

    @abstractmethod
    def __repr__(self):
        pass


def _panic_on_bad_function(fn: Callable, monad: str, method: str, check_impure=True):
    if inspect.iscoroutinefunction(fn):
        raise MonadError(monad, method, f"function '{fn.__name__}' must be sync")
    if check_impure and is_impure(fn):
        raise MonadError(monad, method, f"impure function '{fn.__name__}' can not be used")


def _panic_on_monadic_result(value, fn: Callable, monad: str, method: str):
    if isinstance(value, Triple):
        raise MonadError(
            monad,
            method,
            f"return value {value} of applying function '{fn.__name__}' must not be a Triple entity"
        )


class _Never:
    """A special marker for a violation of the contract"""
    pass


class Right(Triple, Generic[R]):
    """A branch for a value representing a successful result"""

    __slots__ = ["__value"]

    def __init__(self, value: R):
        self.__value = value

    @property
    def value(self) -> R:
        return self.__value

    @property
    def is_right(self) -> bool:
        return True

    @property
    def is_nothing(self) -> bool:
        return False

    def map(self, fn: Callable[[R], V]) -> 'Right[V]':
        """
           Applies a sync function that returns a non-Triple value.
           :raises MonadError: violation of the contract
        """
        _panic_on_bad_function(fn, monad=self.__class__.__name__, method='map')
        result: V = fn(self.value)
        _panic_on_monadic_result(result, fn=fn, monad=self.__class__.__name__, method='map')
        return Right(result)

    @overload
    def bind(self, fn: Callable[[R], 'Right[V]']) -> 'Right[V]': pass
    @overload
    def bind(self, fn: Callable[[R], 'Left[V]']) -> 'Left[V]': pass
    @overload
    def bind(self, fn: Callable[[R], 'Nothing']) -> 'Nothing': pass

    def bind(self, fn):
        """
            Applies a sync function that returns a Triple wrapped value.
            :raises MonadError: violation of the contract
        """
        _panic_on_bad_function(fn, monad=self.__class__.__name__, method='bind')
        return fn(self.value)

    @overload
    def recover_from_left(self, fn: Callable[[L], 'Right[V]']) -> 'Right[R]': pass
    @overload
    def recover_from_left(self, fn: Callable[[L], 'Left[V]']) -> 'Right[R]': pass
    @overload
    def recover_from_left(self, fn: Callable[[L], 'Nothing']) -> 'Right[R]': pass
    @overload
    def recover_from_left(self, fn: Callable[[L], V]) -> 'Right[R]': pass

    def recover_from_left(self, fn):
        """Applies a sync function for recover from error. Always returns itself for this branch."""
        return self

    @overload
    def recover_from_nothing(self, fn: Callable[[], 'Right[V]']) -> 'Right[R]': pass
    @overload
    def recover_from_nothing(self, fn: Callable[[], 'Left[V]']) -> 'Right[R]': pass
    @overload
    def recover_from_nothing(self, fn: Callable[[], 'Nothing']) -> 'Right[R]': pass
    @overload
    def recover_from_nothing(self, fn: Callable[[], V]) -> 'Right[R]': pass

    def recover_from_nothing(self, fn):
        """Applies a sync function for recover from emptiness. Always returns itself for this branch."""
        return self

    def unfold(
            self,
            *,
            right: Callable[[R], V] = lambda v: v,
            left: Callable[[L], W] = lambda w: w,
            nothing: Callable[[], X] = lambda: None
    ) -> V:
        """
            Applies a sync function without wrapping the result. As a rule, it completes the chain.
            :raises MonadError: violation of the contract by 'right'.
        """
        _panic_on_bad_function(right, monad=self.__class__.__name__, method='unfold')
        return right(self.__value)

    @overload
    def ap(self: 'Left[V]', wrapped_val) -> 'Left[V]': pass
    @overload
    def ap(self: 'Nothing', wrapped_val) -> 'Nothing': pass
    @overload
    def ap(self, wrapped_val: 'Left[V]') -> 'Left[V]': pass
    @overload
    def ap(self, wrapped_val: 'Nothing') -> 'Nothing': pass
    @overload
    def ap(self: 'Right[Callable[[V], Right[W]]]', wrapped_val: 'Right[V]') -> 'Right[W]': pass
    @overload
    def ap(self: 'Right[Callable[[V], W]]', wrapped_val: 'Right[V]') -> 'Right[W]': pass
    @overload
    def ap(self: 'Right[Callable[[V], W]]', wrapped_val: 'Right[X]') -> _Never: pass
    @overload
    def ap(self: 'Right[V]', wrapped_val: 'Right[X]') -> _Never: pass

    def ap(self, wrapped_val):
        """
           Applies a value enclosed in a Triple container to sync function also in the container.
           Combines the logic of map and bind, wrapping simple values in a monad.
           :raises MonadError: violation of the contract.
        """
        _panic_on_bad_function(self.value, monad=self.__class__.__name__, method='ap')
        if not wrapped_val.is_right:
            return wrapped_val
        val = getattr(wrapped_val, 'value')
        result = self.value(val)
        return result if isinstance(result, Triple) else Right(result)

    def get_or_else(self, alter: V) -> R:
        return self.__value

    def __repr__(self):
        return f"Right({self.__value})"


class Left(Triple, Generic[L]):
    """A branch for a value representing an error"""

    __slots__ = ["__value"]

    def __init__(self, value: L):
        self.__value = value

    @property
    def value(self) -> L:
        return self.__value

    @property
    def is_right(self) -> bool:
        return False

    @property
    def is_nothing(self) -> bool:
        return False

    def map(self, fn: Callable[[R], V]) -> 'Left[L]':
        return self

    @overload
    def bind(self, fn: Callable[[R], 'Right[V]']) -> 'Left[L]': pass
    @overload
    def bind(self, fn: Callable[[R], 'Left[V]']) -> 'Left[L]': pass
    @overload
    def bind(self, fn: Callable[[R], 'Nothing']) -> 'Left[L]': pass

    def bind(self, fn):
        return self

    @overload
    def recover_from_left(self, fn: Callable[[L], 'Right[V]']) -> 'Right[V]': pass
    @overload
    def recover_from_left(self, fn: Callable[[L], 'Left[V]']) -> 'Left[V]': pass
    @overload
    def recover_from_left(self, fn: Callable[[L], 'Nothing']) -> 'Nothing': pass
    @overload
    def recover_from_left(self, fn: Callable[[L], V]) -> 'Right[V]': pass

    def recover_from_left(self, fn):
        """
           Applies a sync function for recover from error.
           Combines the logic of map and bind, wrapping simple values in a Triple.
           :raises MonadError: violation of the contract.
        """
        _panic_on_bad_function(fn, monad=self.__class__.__name__, method='recover_from_left')
        result = fn(self.value)
        return result if isinstance(result, Triple) else Right(result)

    @overload
    def recover_from_nothing(self, fn: Callable[[], 'Right[V]']) -> 'Left[L]': pass
    @overload
    def recover_from_nothing(self, fn: Callable[[], 'Left[V]']) -> 'Left[L]': pass
    @overload
    def recover_from_nothing(self, fn: Callable[[], 'Nothing']) -> 'Left[L]': pass
    @overload
    def recover_from_nothing(self, fn: Callable[[], V]) -> 'Left[L]': pass

    def recover_from_nothing(self, fn):
        """Applies a sync function for recover from emptiness. Always returns itself for this branch."""
        return self

    def unfold(
            self,
            *,
            right: Callable[[R], V] = lambda v: v,
            left: Callable[[L], W] = lambda w: w,
            nothing: Callable[[], X] = lambda: None
    ) -> W:
        """
            Applies a sync function without wrapping the result. As a rule, it completes the chain.
            :raises MonadError: violation of the contract by 'left'.
        """
        _panic_on_bad_function(left, monad=self.__class__.__name__, method='unfold')
        return left(self.__value)

    @overload
    def ap(self: 'Left[V]', wrapped_val) -> 'Left[V]': pass
    @overload
    def ap(self: 'Nothing', wrapped_val) -> 'Nothing': pass
    @overload
    def ap(self, wrapped_val: 'Left[V]') -> 'Left[V]': pass
    @overload
    def ap(self, wrapped_val: 'Nothing') -> 'Nothing': pass
    @overload
    def ap(self: 'Right[Callable[[V], Right[W]]]', wrapped_val: 'Right[V]') -> 'Right[W]': pass
    @overload
    def ap(self: 'Right[Callable[[V], W]]', wrapped_val: 'Right[V]') -> 'Right[W]': pass
    @overload
    def ap(self: 'Right[Callable[[V], W]]', wrapped_val: 'Right[X]') -> _Never: pass
    @overload
    def ap(self: 'Right[V]', wrapped_val: 'Right[X]') -> _Never: pass

    def ap(self, wrapped_val):
        return self

    def get_or_else(self, alter: V) -> V:
        return alter

    def __repr__(self):
        return f"Left({self.__value})"


class Nothing(Triple):
    """A branch for an empty result"""

    __slots__ = []

    @property
    def is_right(self) -> bool:
        return False

    @property
    def is_nothing(self) -> bool:
        return True

    def map(self, fn: Callable[[R], V]) -> 'Nothing':
        return self

    @overload
    def bind(self, fn: Callable[[R], 'Right[V]']) -> 'Nothing': pass
    @overload
    def bind(self, fn: Callable[[R], 'Left[V]']) -> 'Nothing': pass
    @overload
    def bind(self, fn: Callable[[R], 'Nothing']) -> 'Nothing': pass

    def bind(self, fn):
        return self

    @overload
    def recover_from_left(self, fn: Callable[[L], 'Right[V]']) -> 'Nothing': pass
    @overload
    def recover_from_left(self, fn: Callable[[L], 'Left[V]']) -> 'Nothing': pass
    @overload
    def recover_from_left(self, fn: Callable[[L], 'Nothing']) -> 'Nothing': pass
    @overload
    def recover_from_left(self, fn: Callable[[L], V]) -> 'Nothing': pass

    def recover_from_left(self, fn):
        """Applies a sync function for recover from error. Always returns itself for this branch."""
        return self

    @overload
    def recover_from_nothing(self, fn: Callable[[], 'Right[V]']) -> 'Right[V]': pass
    @overload
    def recover_from_nothing(self, fn: Callable[[], 'Left[V]']) -> 'Left[V]': pass
    @overload
    def recover_from_nothing(self, fn: Callable[[], 'Nothing']) -> 'Nothing': pass
    @overload
    def recover_from_nothing(self, fn: Callable[[], V]) -> 'Right[V]': pass

    def recover_from_nothing(self, fn):
        """
           Applies a sync function for recover from emptiness.
           Combines the logic of map and bind, wrapping simple values in a Triple.
           :raises MonadError: violation of the contract.
        """
        _panic_on_bad_function(fn, monad=self.__class__.__name__, method='recover_from_nothing')
        result = fn()
        return result if isinstance(result, Triple) else Right(result)

    def unfold(
            self,
            *,
            right: Callable[[R], V] = lambda v: v,
            left: Callable[[L], W] = lambda w: w,
            nothing: Callable[[], X] = lambda: None
    ) -> V:
        """
            Applies a sync function without wrapping the result. As a rule, it completes the chain.
            :raises MonadError: violation of the contract by 'nothing'.
        """
        _panic_on_bad_function(nothing, monad=self.__class__.__name__, method='unfold')
        return nothing()

    def get_or_else(self, alter: V) -> V:
        return alter

    @overload
    def ap(self: 'Left[V]', wrapped_val) -> 'Left[V]': pass
    @overload
    def ap(self: 'Nothing', wrapped_val) -> 'Nothing': pass
    @overload
    def ap(self, wrapped_val: 'Left[V]') -> 'Left[V]': pass
    @overload
    def ap(self, wrapped_val: 'Nothing') -> 'Nothing': pass
    @overload
    def ap(self: 'Right[Callable[[V], Right[W]]]', wrapped_val: 'Right[V]') -> 'Right[W]': pass
    @overload
    def ap(self: 'Right[Callable[[V], W]]', wrapped_val: 'Right[V]') -> 'Right[W]': pass
    @overload
    def ap(self: 'Right[Callable[[V], W]]', wrapped_val: 'Right[X]') -> _Never: pass
    @overload
    def ap(self: 'Right[V]', wrapped_val: 'Right[X]') -> _Never: pass

    def ap(self, wrapped_val):
        return self

    def __repr__(self):
        return f"Nothing()"


Params = ParamSpec('Params')


class TUtils:
    """Several useful auxiliary functions - static methods"""

    @staticmethod
    def unit(value: R) -> Right[R]:
        """Wraps a non-Triple value in a Right container"""
        return Right(value)

    @staticmethod
    def from_nullable(value: R, predicate: Callable[[R], bool] = lambda v: bool(v)) -> Union[Right[R], Nothing]:
        """Wraps a non-Triple value in a Right container if the predicate returns true, otherwise - Nothing"""
        return Right(value) if predicate(value) else Nothing()

    @staticmethod
    def from_try(fn: Callable[Params, V]) -> Callable[Params, Union[Right[V], Left[Exception]]]:
        """
           Performs a sync function, catching possible errors - heirs of 'Exception'.
           MonadError is not suppressed.
           :raises MonadError: violation of the synchronicity of the function.
        """
        _panic_on_bad_function(fn, monad=TUtils.__name__, method='from_try')

        def from_try_inner(*args: Params.args, **kwargs: Params.kwargs) -> Union[Right[V], Left[Exception]]:
            try:
                result: V = fn(*args, **kwargs)
                return Right(result)
            except Exception as err:
                if isinstance(err, (MonadError, KeyboardInterrupt)):
                    raise err
                return Left(err)

        return wraps(fn)(from_try_inner)

    @staticmethod
    def lift(curried, *wrapped_args: Triple):
        """Applies Triple-wrapped positional arguments to a curried function(not wrapped) through 'ap' method"""
        result = Right(curried)
        for arg in wrapped_args:
            result = result.ap(arg)
        return result

    @staticmethod
    def is_bad(value) -> bool:
        """Check for bad Triple entity"""
        return isinstance(value, Triple) and not value.is_right

    @staticmethod
    def closer(func: Callable[..., R]) -> Callable[..., Union[Left, Nothing, R]]:
        """Sync decorator - if one of the arguments is a "bad" Triple entity, it immediately returns it.
           Otherwise, it calls the function with the passed arguments, automatically unwraps "good" Triple entities.
        """
        def closer_wrapper(*args, **kwargs) -> Union[Left, Nothing, R]:
            for arg in args:
                if TUtils.is_bad(arg):
                    return arg
            for arg in kwargs.values():
                if TUtils.is_bad(arg):
                    return arg
            unwrapped_pos = [getattr(arg, 'value') if isinstance(arg, Triple) else arg for arg in args]
            unwrapped_named = {nm: getattr(v, 'value') if isinstance(v, Triple) else v for nm, v in kwargs.items()}
            return func(*unwrapped_pos, **unwrapped_named)
        return wraps(func)(closer_wrapper)

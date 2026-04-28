from abc import ABC, abstractmethod
from typing import TypeVar, ParamSpec, Generic, Union, Never
from collections.abc import Callable
from functools import wraps

from mafunca.common.exceptions import ImpureMarkError, MonadError
import mafunca.common._panics as panics # noqa


__all__ = [
    'impure',
    'is_impure',
    'Triple',
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


_Ok = TypeVar('_Ok')
_NewOk = TypeVar('_NewOk')
_Bad = TypeVar('_Bad')
_NewBad = TypeVar('_NewBad')

_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")


class Triple(ABC, Generic[_Ok, _Bad]):
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
    def map(self, fn: Callable[[_Ok], _NewOk]) -> 'Triple[_NewOk, _Bad]':
        pass

    @abstractmethod
    def bind(
        self,
        fn: Callable[[_Ok], 'Triple[_NewOk, _NewBad]']
    ) -> 'Triple[_NewOk, Union[_Bad, _NewBad]]':
        pass

    @abstractmethod
    def recover_from_left(
        self,
        fn: Callable[[_Bad], Union['Triple[_NewOk, _NewBad]', _NewOk]]
    ) -> 'Triple[_NewOk, _NewBad]':
        pass

    @abstractmethod
    def recover_from_nothing(
        self,
        fn: Callable[[], Union['Triple[_NewOk, _NewBad]', _NewOk]]
    ) -> 'Triple[_NewOk, _NewBad]':
        pass

    @abstractmethod
    def unfold(
        self,
        *,
        right: Callable[[_Ok], _T1] = lambda v: v,
        left: Callable[[_Bad], _T2] = lambda w: w,
        nothing: Callable[[], _T3] = lambda: None
    ) -> Union[_T1, _T2, _T3]:
        pass

    @abstractmethod
    def ap(self, wrapped_val: 'Triple[_T1, _NewBad]'):
        pass

    @abstractmethod
    def get_or_else(self, alter: _NewOk) -> Union[_Ok, _NewOk]:
        pass

    @abstractmethod
    def __repr__(self):
        pass


def _panic_on_bad_function(fn: Callable, monad: str, method: str, check_impure=True):
    panics.on_coroutine(fn, monad_name=monad, method=method)
    if check_impure and is_impure(fn):
        raise MonadError(monad, method, f"impure function '{fn.__name__}' can not be used")


class Right(Triple[_Ok, Never], Generic[_Ok]):
    """A branch for a value representing a successful result"""

    __slots__ = ["_value"]

    def __init__(self, value: _Ok):
        self._value = value

    @property
    def value(self) -> _Ok:
        return self._value

    @property
    def is_right(self) -> bool:
        return True

    @property
    def is_nothing(self) -> bool:
        return False

    def map(self, fn: Callable[[_Ok], _NewOk]) -> 'Right[_NewOk]':
        """
           Applies a sync function that returns a non-Triple value.
           :raises MonadError: violation of the contract
        """
        _panic_on_bad_function(fn, monad=self.__class__.__name__, method='map')
        result = fn(self._value)
        return Right(result)

    def bind(self, fn: Callable[[_Ok], Triple[_NewOk, _NewBad]]) -> Triple[_NewOk, _NewBad]:
        """
            Applies a sync function that returns a Triple wrapped value.
            :raises MonadError: violation of the contract
        """
        _panic_on_bad_function(fn, monad=self.__class__.__name__, method='bind')
        return fn(self._value)

    def recover_from_left(
        self,
        fn: Callable[[Never], Union[Triple[_NewOk, _NewBad], _NewOk]]
    ) -> 'Right[_Ok]':
        return self

    def recover_from_nothing(
        self,
        fn: Callable[[], Union[Triple[_NewOk, _NewBad], _NewOk]]
    ) -> 'Right[_Ok]':
        return self

    def unfold(
        self,
        *,
        right: Callable[[_Ok], _T1] = lambda v: v,
        left: Callable[[Never], _T2] = lambda w: w,
        nothing: Callable[[], _T3] = lambda: None
    ) -> _T1:
        """
            Applies a sync function without wrapping the result. As a rule, it completes the chain.
            :raises MonadError: violation of the contract by 'right'.
        """
        _panic_on_bad_function(right, monad=self.__class__.__name__, method='unfold')
        return right(self._value)

    def ap(self: 'Right[Callable[[_T1], _T2]]', wrapped_val: Triple[_T1, _NewBad]) -> Triple[_T2, _NewBad]:
        """
           Applies a value enclosed in a Triple container to sync function also in the container.
           Combines the logic of map and bind, wrapping simple values in a monad.
           :raises MonadError: violation of the contract.
        """
        _panic_on_bad_function(self._value, monad=self.__class__.__name__, method='ap')
        if not wrapped_val.is_right:
            return wrapped_val
        val = getattr(wrapped_val, 'value')
        result = self._value(val)
        return result if isinstance(result, Triple) else Right(result)

    def get_or_else(self, alter: _NewOk) -> _Ok:
        return self._value

    def __repr__(self):
        return f"Right({self._value})"


class Left(Triple[Never, _Bad], Generic[_Bad]):
    """A branch for a value representing an error"""

    __slots__ = ["_value"]

    def __init__(self, value: _Bad):
        self._value = value

    @property
    def value(self) -> _Bad:
        return self._value

    @property
    def is_right(self) -> bool:
        return False

    @property
    def is_nothing(self) -> bool:
        return False

    def map(self, fn: Callable[[Never], _NewOk]) -> 'Left[_Bad]':
        return self

    def bind(self, fn: Callable[[Never], Triple[_NewOk, _NewBad]]) -> 'Left[_Bad]':
        return self

    def recover_from_left(
        self,
        fn: Callable[[_Bad], Union[Triple[_NewOk, _NewBad], _NewOk]]
    ) -> Triple[_NewOk, _NewBad]:
        """
           Applies a sync function for recover from error.
           Combines the logic of map and bind, wrapping simple values in a Triple.
           :raises MonadError: violation of the contract.
        """
        _panic_on_bad_function(fn, monad=self.__class__.__name__, method='recover_from_left')
        result = fn(self._value)
        return result if isinstance(result, Triple) else Right(result)

    def recover_from_nothing(
        self,
        fn: Callable[[], Union[Triple[_NewOk, _NewBad], _NewOk]]
    ) -> 'Left[_Bad]':
        return self

    def unfold(
        self,
        *,
        right: Callable[[Never], _T1] = lambda v: v,
        left: Callable[[_Bad], _T2] = lambda w: w,
        nothing: Callable[[], _T3] = lambda: None
    ) -> _T2:
        """
            Applies a sync function without wrapping the result. As a rule, it completes the chain.
            :raises MonadError: violation of the contract by 'left'.
        """
        _panic_on_bad_function(left, monad=self.__class__.__name__, method='unfold')
        return left(self._value)

    def ap(self, wrapped_val: Triple[_T1, _NewBad]) -> 'Left[_Bad]':
        return self

    def get_or_else(self, alter: _NewOk) -> _NewOk:
        return alter

    def __repr__(self):
        return f"Left({self._value})"


class Nothing(Triple[Never, Never]):
    """A branch for an empty result"""

    __slots__ = []

    @property
    def is_right(self) -> bool:
        return False

    @property
    def is_nothing(self) -> bool:
        return True

    def map(self, fn: Callable[[Never], _NewOk]) -> 'Nothing':
        return self

    def bind(self, fn: Callable[[Never], Triple[_NewOk, _NewBad]]) -> 'Nothing':
        return self

    def recover_from_left(
        self,
        fn: Callable[[Never], Union[Triple[_NewOk, _NewBad], _NewOk]]
    ) -> 'Nothing':
        return self

    def recover_from_nothing(
        self,
        fn: Callable[[], Union[Triple[_NewOk, _NewBad], _NewOk]]
    ) -> Triple[_NewOk, _NewBad]:
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
        right: Callable[[Never], _T1] = lambda v: v,
        left: Callable[[Never], _T2] = lambda w: w,
        nothing: Callable[[], _T3] = lambda: None
    ) -> _T3:
        """
            Applies a sync function without wrapping the result. As a rule, it completes the chain.
            :raises MonadError: violation of the contract by 'nothing'.
        """
        _panic_on_bad_function(nothing, monad=self.__class__.__name__, method='unfold')
        return nothing()

    def ap(self, wrapped_val: Triple[_T1, _NewBad]) -> 'Nothing':
        return self

    def get_or_else(self, alter: _NewOk) -> _NewOk:
        return alter

    def __repr__(self):
        return f"Nothing()"


Params = ParamSpec('Params')


class TUtils:
    """Several useful auxiliary functions - static methods"""

    @staticmethod
    def of(value: _Ok) -> Right[_Ok]:
        """Wraps a non-Triple value in a Right container"""
        return Right(value)

    @staticmethod
    def from_nullable(
        value: _Ok,
        predicate: Callable[[_Ok], bool] = lambda v: v is not None
    ) -> Union[Right[_Ok], Nothing]:
        """Wraps a non-Triple value in a Right container if the predicate returns true, otherwise - Nothing"""
        return Right(value) if predicate(value) else Nothing()

    @staticmethod
    def from_try(fn: Callable[Params, _Ok]) -> Callable[Params, Union[Right[_Ok], Left[Exception]]]:
        """
           Performs a sync function, catching possible errors - heirs of 'Exception'.
           MonadError is not suppressed.
           :raises MonadError: violation of the synchronicity of the function.
        """
        _panic_on_bad_function(fn, monad=TUtils.__name__, method='from_try')

        def from_try_inner(*args: Params.args, **kwargs: Params.kwargs) -> Union[Right[_Ok], Left[Exception]]:
            try:
                result: _Ok = fn(*args, **kwargs)
                return Right(result)
            except Exception as err:
                if isinstance(err, MonadError):
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
    def is_triple(value) -> bool:
        """Check for Triple entity"""
        return isinstance(value, Triple)

    @staticmethod
    def is_bad(value) -> bool:
        """Check for bad Triple entity"""
        return isinstance(value, Triple) and not value.is_right

    @staticmethod
    def closer(func: Callable[..., _Ok]) -> Callable[..., Union[Left, Nothing, _Ok]]:
        """Sync decorator - if one of the arguments is a "bad" Triple entity, it immediately returns it.
           Otherwise, it calls the function with the passed arguments, automatically unwraps "good" Triple entities.
        """
        def closer_wrapper(*args, **kwargs) -> Union[Left, Nothing, _Ok]:
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

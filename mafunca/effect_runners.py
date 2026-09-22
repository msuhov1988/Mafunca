from dataclasses import dataclass, field
from collections.abc import Callable, Awaitable
from time import sleep
import asyncio
from typing import TypeVar, TypeAlias, ParamSpec, Any, cast

from mafunca.common.exceptions import RetryByExceptionError, RetryByValueError, RetryBadPauseError, MonadError
from mafunca.result.build import Success, Fail, Result
from mafunca.eff.build import Eff
from mafunca.eff.build import _Pure, _Delay, _Retry  # type: ignore # noqa
from mafunca.eff.build import _Bind, _Catch, _Ensure, _Bracket  # type: ignore # noqa
from mafunca.aff.build import Aff
from mafunca.aff.build import _PureAsync, _DelayAsync, _DelayThreadAsync, _RetryAsync  # type: ignore # noqa
from mafunca.aff.build import _BindAsync, _CatchAsync, _EnsureAsync, _BracketAsync  # type: ignore # noqa


__all__ = ["run", "run_safe", "run_async", "run_safe_async"]


A = TypeVar("A")
B = TypeVar("B")
E = TypeVar("E")

Args = ParamSpec('Args')


_CONTRACT_VIOLATION = 'check all methods that require a specific type of monad to be returned'


def _raise_and_wrap(error: Exception) -> Fail[Exception]:
    """Add stack unwinding for errors related to exhausted retries"""
    try:
        raise error
    except Exception as exc:
        return Fail(exc)


def _sync_perform(fn: Callable[Args, A], *args: Args.args, **kwargs: Args.kwargs) -> Result[A, BaseException]:
    try:
        return Success(fn(*args, **kwargs))
    except BaseException as err:
        return Fail(err)


def _sync_perform_with_retry(node: _Retry[A], previous_result: object, is_assigned: bool) -> Result[A, BaseException]:
    value, either_result = None, None
    for attempt in range(1, node.total_attempts + 1):
        either_result = _sync_perform(node.thunk)
        if isinstance(either_result, Success):
            value = either_result.value
            either_retry_flag = _sync_perform(node.retry_on_result, value)
            if isinstance(either_retry_flag, Fail):
                return either_retry_flag
            if not either_retry_flag.value:
                return Success(value)
        else:
            if not isinstance(either_result.error, node.retry_on_exceptions):
                return either_result

        if attempt < node.total_attempts:
            either_pause = _sync_perform(node.pause_seconds_between, attempt)
            if isinstance(either_pause, Fail):
                return either_pause
            pause = either_pause.value
            if pause < 0:
                return _raise_and_wrap(RetryBadPauseError(node.step_name))
            sleep(pause)

    if isinstance(either_result, Fail):
        error = cast(Exception, either_result.error)  # retry on BaseException is prohibited at the type level. Only on Exception  
        retry_error = RetryByExceptionError(previous_result, is_assigned, error, node.step_name)
    else:
        retry_error = RetryByValueError(previous_result, is_assigned, value, node.step_name)
    return _raise_and_wrap(retry_error)


async def _async_perform(
        fn: Callable[[], Awaitable[A]],
        wait_seconds: int | float | None
) -> Result[A, BaseException]:
    try:
        if wait_seconds is None:
            return Success(await fn())
        else:
            async with asyncio.timeout(delay=wait_seconds):
                return Success(await fn())
    except BaseException as err:
        return Fail(err)


async def _async_perform_thread(fn: Callable[[], A]) -> Result[A, BaseException]:
    try:
        result = await asyncio.to_thread(fn)
        return Success(result)
    except BaseException as err:
        return Fail(err)


async def _async_perform_with_retry(
        node: _RetryAsync[A],
        previous_result: object,
        is_assigned: bool
) -> Result[A, BaseException]:
    value, either_result = None, None
    for attempt in range(1, node.total_attempts + 1):
        either_result = await _async_perform(node.thunk, node.wait_seconds_on_attempt)
        if isinstance(either_result, Success):
            value = either_result.value
            either_retry_flag = _sync_perform(node.retry_on_result, value)
            if isinstance(either_retry_flag, Fail):
                return either_retry_flag
            if not either_retry_flag.value:
                return Success(value)
        else:
            if not isinstance(either_result.error, node.retry_on_exceptions):
                return either_result

        if attempt < node.total_attempts:
            either_pause = _sync_perform(node.pause_seconds_between, attempt)
            if isinstance(either_pause, Fail):
                return either_pause
            pause = either_pause.value
            if pause < 0:
                return _raise_and_wrap(RetryBadPauseError(node.step_name))
            try:
                await asyncio.sleep(pause)
            except BaseException as err:
                return Fail(err)

    if isinstance(either_result, Fail): 
        error = cast(Exception, either_result.error)  # retry on BaseException is prohibited at the type level. Only on Exception      
        retry_error = RetryByExceptionError(previous_result, is_assigned, error, node.step_name)
    else:
        retry_error = RetryByValueError(previous_result, is_assigned, value, node.step_name)
    return _raise_and_wrap(retry_error)


@dataclass(frozen=True, slots=True)
class _FrameContinuation:
    continuation: Callable[[Any], Eff[Any] | Aff[Any]]


@dataclass(frozen=True, slots=True)
class _FrameCatch:
    exc_type: type[Any]
    catcher: Callable[[Any], Eff[Any] | Aff[Any]]


_FinalizerOutput: TypeAlias = None | Result[None, Any]


@dataclass(frozen=True, slots=True)
class _FrameEnsure:
    finalizer: Eff[_FinalizerOutput] | Aff[_FinalizerOutput]


@dataclass(frozen=True, slots=True)
class _FrameBracketUse:
    use: Callable[[Any], Eff[Any] | Aff[Any]]


@dataclass(frozen=True, slots=True)
class _FrameBracketRelease:
    release: Callable[[Any], Eff[_FinalizerOutput] | Aff[_FinalizerOutput]]


_FrameType: TypeAlias = _FrameContinuation | _FrameCatch | _FrameEnsure | _FrameBracketUse | _FrameBracketRelease


@dataclass(slots=True)
class _Scope:
    node: Eff[Any] | Aff[Any]
    result: Any = None
    is_assigned: bool = False
    error: BaseException | None = None
    frames: list[_FrameType] = field(default_factory=list[_FrameType])


def _set_new_primary_error(
        scope: _Scope,
        new_error: BaseException | None,
        not_replace_cancelled: bool = False
) -> None:
    old_error = scope.error
    if old_error is new_error or new_error is None:
        return
    if old_error is not None:
        if not_replace_cancelled and isinstance(old_error, asyncio.CancelledError):
            old_error.__context__ = new_error
            old_error.__cause__ = None
            old_error.__suppress_context__ = False
            scope.error = old_error
            return   
        new_error.__context__ = old_error
        new_error.__cause__ = None
        new_error.__suppress_context__ = False
    scope.error = new_error


def _enter_ensure_scope(finalizer: Eff[_FinalizerOutput] | Aff[_FinalizerOutput], stack_of_scopes: list[_Scope]) -> _Scope:
    s = _Scope(finalizer)
    stack_of_scopes.append(s)
    return s


def _leave_ensure_scope(stack_of_scopes: list[_Scope], not_replace_cancelled: bool = False) -> _Scope:
    deleted_ensure_scope = stack_of_scopes.pop()
    parent_scope = stack_of_scopes[-1] 
    _set_new_primary_error(
        scope=parent_scope, 
        new_error=deleted_ensure_scope.error, 
        not_replace_cancelled=not_replace_cancelled
        )   
    return parent_scope


@dataclass(frozen=True, slots=True)
class _Empty:
    pass


_EMPTY = _Empty()


#  execution follows two basic branches: no errors, and there are errors
#  finalizer is executed in its own separate scope
#  which allows finalizer to execute regardless of previous step's errors and discard the result upon completion


def run(effect: Eff[A]) -> A:
    """
        Simple synchronous executor - just runs a chain.
        :raises MonadError: violations of the contract
    """
    scope = _Scope(effect)
    stack_of_scopes = [scope]
    bracket_acquires: list[Any] = []
    while True:
        if scope.error is None:
            node = scope.node            
            if isinstance(node, _Bind):
                node = cast(_Bind[Any, Any], node)
                scope.frames.append(_FrameContinuation(continuation=node.continuation))
                scope.node = node.current

            elif isinstance(node, _Catch):
                node = cast(_Catch[Any, Any], node)
                scope.frames.append(_FrameCatch(exc_type=node.exc_type, catcher=node.catcher))
                scope.node = node.current

            elif isinstance(node, _Ensure):
                node = cast(_Ensure[Any, _FinalizerOutput], node)
                scope.frames.append(_FrameEnsure(finalizer=node.finalizer))
                scope.node = node.current

            elif isinstance(node, _Bracket):
                node = cast(_Bracket[Any, Any, Any], node)
                scope.frames.append(_FrameBracketRelease(release=node.release))
                scope.frames.append(_FrameBracketUse(use=node.use))
                bracket_acquires.append(_EMPTY)
                scope.node = node.acquire

            elif isinstance(node, _Delay):
                r = _sync_perform(node.thunk)
                scope.node, scope.error = (_Pure(r.value), scope.error) if isinstance(r, Success) else (node, r.error)

            elif isinstance(node, _Retry):
                r = _sync_perform_with_retry(node=node, previous_result=scope.result, is_assigned=scope.is_assigned)
                scope.node, scope.error = (_Pure(r.value), scope.error) if isinstance(r, Success) else (node, r.error)

            elif isinstance(node, _Pure):
                scope.result, scope.is_assigned = node.value, True
                if not scope.frames:
                    if len(stack_of_scopes) > 1:
                        scope = _leave_ensure_scope(stack_of_scopes=stack_of_scopes)
                    else:
                        return scope.result
                else:
                    frame = scope.frames.pop()
                    if isinstance(frame, _FrameContinuation):
                        r = _sync_perform(frame.continuation, scope.result)
                        scope.node, scope.error = (r.value, scope.error) if isinstance(r, Success) else (node, r.error)
                    elif isinstance(frame, _FrameEnsure):
                        scope = _enter_ensure_scope(finalizer=frame.finalizer, stack_of_scopes=stack_of_scopes)
                    elif isinstance(frame, _FrameBracketUse):
                        bracket_acquires[-1] = scope.result
                        r = _sync_perform(frame.use, scope.result) 
                        scope.node, scope.error = (r.value, scope.error) if isinstance(r, Success) else (node, r.error)  
                    elif isinstance(frame, _FrameBracketRelease):
                        resource = bracket_acquires.pop()                        
                        r = _sync_perform(frame.release, resource) 
                        if isinstance(r, Success):
                            scope = _enter_ensure_scope(finalizer=r.value, stack_of_scopes=stack_of_scopes)
                        else:
                            scope.error = r.error

            else:
                raise MonadError(monad=type(effect).__name__, method='run', message=_CONTRACT_VIOLATION)

        else:
            if not scope.frames:
                if len(stack_of_scopes) > 1:
                    scope = _leave_ensure_scope(stack_of_scopes=stack_of_scopes)
                else:
                    raise scope.error
            else:
                frame = scope.frames.pop()
                if isinstance(frame, _FrameCatch) and isinstance(scope.error, frame.exc_type):
                    r = _sync_perform(frame.catcher, scope.error)
                    if isinstance(r, Success):
                        scope.node, scope.error = r.value, None
                    else:
                        _set_new_primary_error(scope=scope, new_error=r.error)
                elif isinstance(frame, _FrameEnsure):
                    scope = _enter_ensure_scope(finalizer=frame.finalizer, stack_of_scopes=stack_of_scopes)
                elif isinstance(frame, _FrameBracketRelease):
                    resource = bracket_acquires.pop()
                    if resource is not _EMPTY:
                        r = _sync_perform(frame.release, resource) 
                        if isinstance(r, Success):
                            scope = _enter_ensure_scope(finalizer=r.value, stack_of_scopes=stack_of_scopes)
                        else:
                            _set_new_primary_error(scope=scope, new_error=r.error)   


def run_safe(effect: Eff[A]) -> Result[A, Exception]:
    """
        Synchronous executor - runs a chain, catching possible errors - heirs of 'Exception'
        :raises MonadError: violations of the contract
    """
    try:        
        return Success(run(effect))
    except Exception as err:
        return Fail(err)


#  execution follows two basic branches: no errors, and there are errors
#  finalizer is executed in its own separate scope
#  which allows finalizer to execute regardless of previous step's errors and discard the result upon completion


async def run_async(effect: Aff[A]) -> A:
    """
        Simple asynchronous executor - just runs a chain.
        :raises MonadError: violations of the contract
    """
    scope = _Scope(effect)
    stack_of_scopes = [scope]
    bracket_acquires: list[Any] = []
    while True:
        if scope.error is None:
            node = scope.node
            if isinstance(node, _BindAsync):
                node = cast(_BindAsync[Any, Any], node)
                scope.frames.append(_FrameContinuation(continuation=node.continuation))
                scope.node = node.current

            elif isinstance(node, _CatchAsync):
                node = cast(_CatchAsync[Any, Any], node)
                scope.frames.append(_FrameCatch(exc_type=node.exc_type, catcher=node.catcher))
                scope.node = node.current

            elif isinstance(node, _EnsureAsync):
                node = cast(_EnsureAsync[Any, _FinalizerOutput], node)
                scope.frames.append(_FrameEnsure(finalizer=node.finalizer))
                scope.node = node.current

            elif isinstance(node, _BracketAsync):
                node = cast(_BracketAsync[Any, Any, Any], node)
                scope.frames.append(_FrameBracketRelease(release=node.release))
                scope.frames.append(_FrameBracketUse(use=node.use))
                bracket_acquires.append(_EMPTY)
                scope.node = node.acquire

            elif isinstance(node, _DelayAsync):
                r = await _async_perform(node.thunk, wait_seconds=node.wait_seconds)
                scope.node, scope.error = (_PureAsync(r.value), scope.error) if isinstance(r, Success) else (node, r.error)

            elif isinstance(node, _DelayThreadAsync):
                r = await _async_perform_thread(node.thunk)
                scope.node, scope.error = (_PureAsync(r.value), scope.error) if isinstance(r, Success) else (node, r.error)

            elif isinstance(node, _RetryAsync):                
                r = await _async_perform_with_retry(node, previous_result=scope.result, is_assigned=scope.is_assigned)
                scope.node, scope.error = (_PureAsync(r.value), scope.error) if isinstance(r, Success) else (node, r.error)                

            elif isinstance(node, _PureAsync):
                scope.result, scope.is_assigned = node.value, True
                if not scope.frames:
                    if len(stack_of_scopes) > 1:
                        scope = _leave_ensure_scope(stack_of_scopes=stack_of_scopes, not_replace_cancelled=True)
                    else:
                        return scope.result
                else:
                    frame = scope.frames.pop()
                    if isinstance(frame, _FrameContinuation):
                        r = _sync_perform(frame.continuation, scope.result)
                        scope.node, scope.error = (r.value, scope.error) if isinstance(r, Success) else (node, r.error)
                    elif isinstance(frame, _FrameEnsure):
                        scope = _enter_ensure_scope(finalizer=frame.finalizer, stack_of_scopes=stack_of_scopes)
                    elif isinstance(frame, _FrameBracketUse):
                        bracket_acquires[-1] = scope.result
                        r = _sync_perform(frame.use, scope.result) 
                        scope.node, scope.error = (r.value, scope.error) if isinstance(r, Success) else (node, r.error)  
                    elif isinstance(frame, _FrameBracketRelease):
                        resource = bracket_acquires.pop()                        
                        r = _sync_perform(frame.release, resource) 
                        if isinstance(r, Success):
                            scope = _enter_ensure_scope(finalizer=r.value, stack_of_scopes=stack_of_scopes)
                        else:
                            scope.error = r.error

            else:
                raise MonadError(monad=type(effect).__name__, method='run_async', message=_CONTRACT_VIOLATION)

        else:
            if not scope.frames:
                if len(stack_of_scopes) > 1:
                    scope = _leave_ensure_scope(stack_of_scopes=stack_of_scopes, not_replace_cancelled=True)
                else:
                    raise scope.error
            else:
                frame = scope.frames.pop()
                if isinstance(frame, _FrameCatch) and isinstance(scope.error, frame.exc_type):
                    r = _sync_perform(frame.catcher, scope.error)
                    if isinstance(r, Success):
                        scope.node, scope.error = r.value, None
                    else:
                        _set_new_primary_error(scope=scope, new_error=r.error)
                elif isinstance(frame, _FrameEnsure):
                    scope = _enter_ensure_scope(finalizer=frame.finalizer, stack_of_scopes=stack_of_scopes)
                elif isinstance(frame, _FrameBracketRelease):
                    resource = bracket_acquires.pop()
                    if resource is not _EMPTY:
                        r = _sync_perform(frame.release, resource) 
                        if isinstance(r, Success):
                            scope = _enter_ensure_scope(finalizer=r.value, stack_of_scopes=stack_of_scopes)
                        else:
                            _set_new_primary_error(scope=scope, new_error=r.error, not_replace_cancelled=True)


async def run_safe_async(effect: Aff[A]) -> Result[A, Exception]:
    """
        Asynchronous executor - runs a chain, catching possible errors - heirs of 'Exception'
        :raises MonadError: violations of the contract
    """
    try:
        return Success(await run_async(effect))
    except Exception as err:
        return Fail(err)

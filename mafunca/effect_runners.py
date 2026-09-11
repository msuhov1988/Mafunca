from dataclasses import dataclass, field
from collections.abc import Callable, Awaitable
from time import sleep
import asyncio
from typing import TypeVar, TypeAlias, ParamSpec, Any, cast

from mafunca.common.exceptions import RetryByExceptionError, RetryByValueError, RetryBadPauseError, MonadError
from mafunca.result.build import Success, Fail, Result
from mafunca.eff.build import Eff
from mafunca.eff.build import _Pure, _Delay, _Retry  # type: ignore # noqa
from mafunca.eff.build import _Bind, _Catch, _Ensure  # type: ignore # noqa
from mafunca.aff.build import Aff
from mafunca.aff.build import _PureAsync, _DelayAsync, _DelayThreadAsync, _RetryAsync  # type: ignore # noqa
from mafunca.aff.build import _BindAsync, _CatchAsync, _EnsureAsync  # type: ignore # noqa


__all__ = ["run", "run_safe", "run_async", "run_safe_async"]


A = TypeVar("A")
B = TypeVar("B")

E = TypeVar("E")
Exc = TypeVar("Exc", bound=Exception)

Args = ParamSpec('Args')


_CONTRACT_VIOLATION = 'check all methods that require a specific type of monad to be returned'


def _raise_and_wrap(error: Exception) -> Fail[Exception]:
    try:
        raise error
    except Exception as exc:
        return Fail(exc)


def _sync_perform(fn: Callable[Args, A], *args: Args.args, **kwargs: Args.kwargs) -> Result[A, Exception]:
    try:
        return Success(fn(*args, **kwargs))
    except Exception as err:
        return Fail(err)


def _sync_perform_with_retry(node: _Retry[A], previous_result: object, is_assigned: bool) -> Result[A, Exception]:
    value, either_result = None, None
    for attempt in range(1, node.total_attempts + 1):
        either_result = _sync_perform(node.thunk)
        if isinstance(either_result, Success):
            value = either_result.value
            either_retry_flag: Result[bool, Exception] = _sync_perform(node.retry_on_result, value)
            if isinstance(either_retry_flag, Fail):
                return either_retry_flag
            if not either_retry_flag.value:
                return Success(value)
        else:
            if not isinstance(either_result.error, node.retry_on_exceptions):
                return either_result

        if attempt < node.total_attempts:
            either_pause: Result[int | float, Exception] = _sync_perform(node.pause_seconds_between, attempt)
            if isinstance(either_pause, Fail):
                return either_pause
            pause = either_pause.value
            if pause < 0:
                return _raise_and_wrap(RetryBadPauseError(node.step_name))
            sleep(pause)

    if isinstance(either_result, Fail):
        retry_error = RetryByExceptionError(previous_result, is_assigned, either_result.error, node.step_name)
    else:
        retry_error = RetryByValueError(previous_result, is_assigned, value, node.step_name)
    return _raise_and_wrap(retry_error)


async def _async_perform(
        fn: Callable[[], Awaitable[A]],
        wait_seconds: int | float | None
) -> Result[A, Exception | asyncio.CancelledError]:
    try:
        if wait_seconds is None:
            return Success(await fn())
        else:
            async with asyncio.timeout(delay=wait_seconds):
                return Success(await fn())
    except (Exception, asyncio.CancelledError) as err:
        return Fail(err)


async def _async_perform_thread(fn: Callable[[], A]) -> Result[A, Exception | asyncio.CancelledError]:
    try:
        result = await asyncio.to_thread(fn)
        return Success(result)
    except (Exception, asyncio.CancelledError) as err:
        return Fail(err)


async def _async_perform_with_retry(
        node: _RetryAsync[A],
        previous_result: object,
        is_assigned: bool
) -> Result[A, Exception | asyncio.CancelledError]:
    value, either_result = None, None
    for attempt in range(1, node.total_attempts + 1):
        either_result = await _async_perform(node.thunk, node.wait_seconds_on_attempt)
        if isinstance(either_result, Success):
            value = either_result.value
            either_retry_flag: Result[bool, Exception] = _sync_perform(node.retry_on_result, value)
            if isinstance(either_retry_flag, Fail):
                return either_retry_flag
            if not either_retry_flag.value:
                return Success(value)
        else:
            if not isinstance(either_result.error, node.retry_on_exceptions):
                return either_result

        if attempt < node.total_attempts:
            either_pause: Result[int | float, Exception] = _sync_perform(node.pause_seconds_between, attempt)
            if isinstance(either_pause, Fail):
                return either_pause
            pause = either_pause.value
            if pause < 0:
                return _raise_and_wrap(RetryBadPauseError(node.step_name))
            try:
                await asyncio.sleep(pause)
            except asyncio.CancelledError as err:
                return Fail(err)

    if isinstance(either_result, Fail): 
        error = cast(Exception, either_result.error)  # retry on asyncio.CancelledError is prohibited at the type level.       
        retry_error = RetryByExceptionError(previous_result, is_assigned, error, node.step_name)
    else:
        retry_error = RetryByValueError(previous_result, is_assigned, value, node.step_name)
    return _raise_and_wrap(retry_error)


@dataclass(frozen=True, slots=True)
class _FrameContinuation:
    continuation: Callable[[Any], Any]


@dataclass(frozen=True, slots=True)
class _FrameCatch:
    exc_type: Any
    catcher: Callable[[Any], Any]


@dataclass(frozen=True, slots=True)
class _FrameEnsure:
    finalizer: Eff[None] | Aff[None]


_FrameType: TypeAlias = _FrameContinuation | _FrameCatch | _FrameEnsure


@dataclass(slots=True)
class _Scope:
    node: Eff[Any] | Aff[Any]
    result: Any = None
    is_assigned: bool = False
    error: BaseException | None = None
    frames: list[_FrameType] = field(default_factory=list[_FrameType])


def _set_new_primary_error(scope: _Scope, new_error: BaseException | None) -> None:
    old_error = scope.error
    if old_error is new_error or new_error is None:
        return
    if old_error is not None:
        new_error.__context__ = old_error
        new_error.__cause__ = None
        new_error.__suppress_context__ = False
    scope.error = new_error


def _enter_ensure_scope(finalizer: Eff[None] | Aff[None], stack_of_scopes: list[_Scope]) -> _Scope:
    s = _Scope(finalizer)
    stack_of_scopes.append(s)
    return s


def _leave_ensure_scope(stack_of_scopes: list[_Scope]) -> _Scope:
    deleted_ensure_scope = stack_of_scopes.pop()
    parent_scope = stack_of_scopes[-1]
    # errors that are not subclasses of Exception are not replaced by finalizer errors
    if parent_scope.error is None or isinstance(parent_scope.error, Exception):
        _set_new_primary_error(scope=parent_scope, new_error=deleted_ensure_scope.error)
    return parent_scope


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
    while True:
        if scope.error is None:
            node = scope.node
            if isinstance(node, _Bind):
                scope.frames.append(_FrameContinuation(continuation=node.continuation))
                scope.node = node.current

            elif isinstance(node, _Catch):
                scope.frames.append(_FrameCatch(exc_type=node.exc_type, catcher=node.catcher))
                scope.node = node.current

            elif isinstance(node, _Ensure):
                scope.frames.append(_FrameEnsure(finalizer=node.finalizer))
                scope.node = node.current

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
    while True:
        if scope.error is None:
            node = scope.node
            if isinstance(node, _BindAsync):
                scope.frames.append(_FrameContinuation(continuation=node.continuation))
                scope.node = node.current

            elif isinstance(node, _CatchAsync):
                scope.frames.append(_FrameCatch(exc_type=node.exc_type, catcher=node.catcher))
                scope.node = node.current

            elif isinstance(node, _EnsureAsync):
                scope.frames.append(_FrameEnsure(finalizer=node.finalizer))
                scope.node = node.current

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

            else:
                raise MonadError(monad=type(effect).__name__, method='run_async', message=_CONTRACT_VIOLATION)

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


async def run_safe_async(effect: Aff[A]) -> Result[A, Exception]:
    """
        Asynchronous executor - runs a chain, catching possible errors - heirs of 'Exception'
        :raises MonadError: violations of the contract
    """
    try:
        return Success(await run_async(effect))
    except Exception as err:
        return Fail(err)

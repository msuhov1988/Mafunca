from dataclasses import dataclass, field
from collections.abc import Callable, Awaitable
from time import sleep
import asyncio
from typing import TypeVar, ParamSpec, Generic, overload, Any

from mafunca.common.exceptions import RetryByExceptionError, RetryByValueError, RetryBadPauseError, MonadError
from mafunca.result import Ok, Err, Result
from mafunca.effect_sync import Effect
from mafunca.effect_sync_transformer import EffectResult
from mafunca.effect_sync import Pure, Delay, Retry  # noqa
from mafunca.effect_sync import Bind, Catch, Ensure  # noqa
from mafunca.effect_async import Aff
from mafunca.effect_async_transformer import AffResult
from mafunca.effect_async import PureAsync, DelayAsync, DelayThreadAsync, RetryAsync  # noqa
from mafunca.effect_async import BindAsync, CatchAsync, EnsureAsync  # noqa


__all__ = ["run", "run_safe", "run_async", "run_safe_async"]


A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)
E = TypeVar("E")

Args = ParamSpec('Args')


_CONTRACT_VIOLATION = 'check all methods that require a specific type of monad to be returned'


def _raise_and_wrap(error: Exception) -> Err[Exception]:
    try:
        raise error
    except Exception as exc:
        return Err(exc)


def _sync_perform(fn: Callable[Args, A], *args: Args.args, **kwargs: Args.kwargs) -> Result[A, Exception]:
    try:
        return Ok(fn(*args, **kwargs))
    except Exception as err:
        return Err(err)


def _sync_perform_with_retry(node: Retry[A], previous_result: B, is_assigned: bool) -> Result[A, Exception]:
    value, either_result = None, None
    for attempt in range(1, node.total_attempts + 1):
        either_result = _sync_perform(node.thunk)
        if isinstance(either_result, Ok):
            value: A = either_result.value
            either_retry_flag: Result[bool, Exception] = _sync_perform(node.retry_on_result, value)
            if isinstance(either_retry_flag, Err):
                return either_retry_flag
            if not either_retry_flag.value:
                return Ok(value)
        else:
            if not isinstance(either_result.error, node.retry_on_exceptions):
                return either_result

        if attempt < node.total_attempts:
            either_pause: Result[int | float, Exception] = _sync_perform(node.pause_seconds_between, attempt)
            if isinstance(either_pause, Err):
                return either_pause
            pause = either_pause.value
            if not isinstance(pause, (int, float)) or pause < 0:
                return _raise_and_wrap(RetryBadPauseError(node.step_name))
            sleep(pause)

    if isinstance(either_result, Err):
        retry_error = RetryByExceptionError(previous_result, is_assigned, either_result.error, node.step_name)
    else:
        retry_error = RetryByValueError(previous_result, is_assigned, value, node.step_name)
    return _raise_and_wrap(retry_error)


async def _async_perform(
        fn: Callable[[], Awaitable[A]],
        wait_seconds: int | float | None
) -> Result[A, Exception | TimeoutError]:
    try:
        if wait_seconds is None:
            return Ok(await fn())
        else:
            async with asyncio.timeout(delay=wait_seconds):
                return Ok(await fn())
    except (Exception, TimeoutError, asyncio.CancelledError) as err:
        return Err(err)


async def _async_perform_thread(fn: Callable[[], A]) -> Result[A, Exception]:
    try:
        result = await asyncio.to_thread(fn)
        return Ok(result)
    except (Exception, asyncio.CancelledError) as err:
        return Err(err)


async def _async_perform_with_retry(
        node: RetryAsync[A],
        previous_result: B,
        is_assigned: bool
) -> Result[A, Exception | TimeoutError]:
    value, either_result = None, None
    for attempt in range(1, node.total_attempts + 1):
        either_result = await _async_perform(node.thunk, node.wait_seconds_on_attempt)
        if isinstance(either_result, Ok):
            value: A = either_result.value
            either_retry_flag: Result[bool, Exception] = _sync_perform(node.retry_on_result, value)
            if isinstance(either_retry_flag, Err):
                return either_retry_flag
            if not either_retry_flag.value:
                return Ok(value)
        else:
            if not isinstance(either_result.error, node.retry_on_exceptions):
                return either_result

        if attempt < node.total_attempts:
            either_pause: Result[int | float, Exception] = _sync_perform(node.pause_seconds_between, attempt)
            if isinstance(either_pause, Err):
                return either_pause
            pause = either_pause.value
            if not isinstance(pause, (int, float)) or pause < 0:
                return _raise_and_wrap(RetryBadPauseError(node.step_name))
            await asyncio.sleep(pause)

    if isinstance(either_result, Err):
        retry_error = RetryByExceptionError(previous_result, is_assigned, either_result.error, node.step_name)
    else:
        retry_error = RetryByValueError(previous_result, is_assigned, value, node.step_name)
    return _raise_and_wrap(retry_error)


@dataclass(frozen=True, slots=True)
class _FrameContinuation(Generic[A, B]):
    continuation: Callable[[A], B]


@dataclass(frozen=True, slots=True)
class _FrameCatch(Generic[Exc, A]):
    exc_type: type[Exc] | type[TimeoutError]
    catcher: Callable[[Exc], A]


@dataclass(frozen=True, slots=True)
class _FrameEnsure:
    finalizer: Effect[None] | Aff[None]


@dataclass(slots=True)
class _Scope:
    node: Effect[Any] | Aff[Any]
    result: Any = None
    is_assigned: bool = False
    error: Exception | None = None
    frames: list[_FrameContinuation | _FrameCatch | _FrameEnsure] = field(default_factory=list)


def _set_new_primary_error(scope: _Scope, new_error: Exception | None) -> None:
    old_error = scope.error
    if old_error is new_error or new_error is None:
        return
    if old_error is not None:
        new_error.__context__ = old_error
        new_error.__cause__ = None
        new_error.__suppress_context__ = False
    scope.error = new_error


def _enter_ensure_scope(finalizer: Effect[None] | Aff[None], stack_of_scopes: list[_Scope]) -> _Scope:
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

@overload
def run(effect: EffectResult[A, E]) -> Result[A, E]: ...
@overload
def run(effect: Effect[A]) -> A: ...


def run(effect):
    """
        Simple synchronous executor - just runs a chain.
        :raises MonadError: violations of the contract
    """
    scope = _Scope(effect.inner if isinstance(effect, EffectResult) else effect)
    stack_of_scopes = [scope]
    while True:
        if scope.error is None:
            node = scope.node
            if isinstance(node, Bind):
                scope.frames.append(_FrameContinuation(continuation=node.continuation))
                scope.node = node.current

            elif isinstance(node, Catch):
                scope.frames.append(_FrameCatch(exc_type=node.exc_type, catcher=node.catcher))
                scope.node = node.current

            elif isinstance(node, Ensure):
                scope.frames.append(_FrameEnsure(finalizer=node.finalizer))
                scope.node = node.current

            elif isinstance(node, Delay):
                r = _sync_perform(node.thunk)
                scope.node, scope.error = (Pure(r.value), scope.error) if isinstance(r, Ok) else (node, r.error)

            elif isinstance(node, Retry):
                r = _sync_perform_with_retry(node=node, previous_result=scope.result, is_assigned=scope.is_assigned)
                scope.node, scope.error = (Pure(r.value), scope.error) if isinstance(r, Ok) else (node, r.error)

            elif isinstance(node, Pure):
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
                        scope.node, scope.error = (r.value, scope.error) if isinstance(r, Ok) else (node, r.error)
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
                    if isinstance(r, Ok):
                        scope.node, scope.error = r.value, None
                    else:
                        _set_new_primary_error(scope=scope, new_error=r.error)
                elif isinstance(frame, _FrameEnsure):
                    scope = _enter_ensure_scope(finalizer=frame.finalizer, stack_of_scopes=stack_of_scopes)


@overload
def run_safe(effect: EffectResult[A, E]) -> Result[Result[A, E], Exception]: ...
@overload
def run_safe(effect: Effect[A]) -> Result[A, Exception]: ...


def run_safe(effect):
    """
        Synchronous executor - runs a chain, catching possible errors - heirs of 'Exception'
        :raises MonadError: violations of the contract
    """
    try:
        return Ok(run(effect))
    except Exception as err:
        return Err(err)


#  execution follows two basic branches: no errors, and there are errors
#  finalizer is executed in its own separate scope
#  which allows finalizer to execute regardless of previous step's errors and discard the result upon completion


@overload
async def run_async(effect: AffResult[A, E]) -> Result[A, E]: ...
@overload
async def run_async(effect: Aff[A]) -> A: ...


async def run_async(effect):
    """
        Simple asynchronous executor - just runs a chain.
        :raises MonadError: violations of the contract
    """
    scope = _Scope(effect.inner if isinstance(effect, AffResult) else effect)
    stack_of_scopes = [scope]
    while True:
        if scope.error is None:
            node = scope.node
            if isinstance(node, BindAsync):
                scope.frames.append(_FrameContinuation(continuation=node.continuation))
                scope.node = node.current

            elif isinstance(node, CatchAsync):
                scope.frames.append(_FrameCatch(exc_type=node.exc_type, catcher=node.catcher))
                scope.node = node.current

            elif isinstance(node, EnsureAsync):
                scope.frames.append(_FrameEnsure(finalizer=node.finalizer))
                scope.node = node.current

            elif isinstance(node, DelayAsync):
                r = await _async_perform(node.thunk, wait_seconds=node.wait_seconds)
                scope.node, scope.error = (PureAsync(r.value), scope.error) if isinstance(r, Ok) else (node, r.error)

            elif isinstance(node, DelayThreadAsync):
                r = await _async_perform_thread(node.thunk)
                scope.node, scope.error = (PureAsync(r.value), scope.error) if isinstance(r, Ok) else (node, r.error)

            elif isinstance(node, RetryAsync):
                r = await _async_perform_with_retry(node, previous_result=scope.result, is_assigned=scope.is_assigned)
                scope.node, scope.error = (PureAsync(r.value), scope.error) if isinstance(r, Ok) else (node, r.error)

            elif isinstance(node, PureAsync):
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
                        scope.node, scope.error = (r.value, scope.error) if isinstance(r, Ok) else (node, r.error)
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
                    if isinstance(r, Ok):
                        scope.node, scope.error = r.value, None
                    else:
                        _set_new_primary_error(scope=scope, new_error=r.error)
                elif isinstance(frame, _FrameEnsure):
                    scope = _enter_ensure_scope(finalizer=frame.finalizer, stack_of_scopes=stack_of_scopes)


@overload
async def run_safe_async(effect: AffResult[A, E]) -> Result[Result[A, E], Exception | TimeoutError]: ...
@overload
async def run_safe_async(effect: Aff[A]) -> Result[A, Exception | TimeoutError]: ...


async def run_safe_async(effect):
    """
        Asynchronous executor - runs a chain, catching TimeoutError and another possible errors - heirs of 'Exception'
        :raises MonadError: violations of the contract
    """
    try:
        return Ok(await run_async(effect))
    except (Exception, TimeoutError) as err:
        return Err(err)

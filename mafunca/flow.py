from collections.abc import Callable
from typing import TypeVar, overload, Any


T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
T4 = TypeVar("T4")
T5 = TypeVar("T5")
T6 = TypeVar("T6")
T7 = TypeVar("T7")
T8 = TypeVar("T8")
T9 = TypeVar("T9")


@overload
def flow(
        value: T1,
        /
) -> T1: ...


@overload
def flow(
        value: T1,
        fn1: Callable[[T1], T2],
        /
) -> T2: ...


@overload
def flow(
        value: T1,
        fn1: Callable[[T1], T2],
        fn2: Callable[[T2], T3],
        /
) -> T3: ...


@overload
def flow(
        value: T1,
        fn1: Callable[[T1], T2],
        fn2: Callable[[T2], T3],
        fn3: Callable[[T3], T4],
        /
) -> T4: ...


@overload
def flow(
        value: T1,
        fn1: Callable[[T1], T2],
        fn2: Callable[[T2], T3],
        fn3: Callable[[T3], T4],
        fn4: Callable[[T4], T5],
        /
) -> T5: ...


@overload
def flow(
        value: T1,
        fn1: Callable[[T1], T2],
        fn2: Callable[[T2], T3],
        fn3: Callable[[T3], T4],
        fn4: Callable[[T4], T5],
        fn5: Callable[[T5], T6],
        /
) -> T6: ...


@overload
def flow(
        value: T1,
        fn1: Callable[[T1], T2],
        fn2: Callable[[T2], T3],
        fn3: Callable[[T3], T4],
        fn4: Callable[[T4], T5],
        fn5: Callable[[T5], T6],
        fn6: Callable[[T6], T7],
        /
) -> T7: ...


@overload
def flow(
        value: T1,
        fn1: Callable[[T1], T2],
        fn2: Callable[[T2], T3],
        fn3: Callable[[T3], T4],
        fn4: Callable[[T4], T5],
        fn5: Callable[[T5], T6],
        fn6: Callable[[T6], T7],
        fn7: Callable[[T7], T8],
        /
) -> T8: ...


@overload
def flow(
        value: T1,
        fn1: Callable[[T1], T2],
        fn2: Callable[[T2], T3],
        fn3: Callable[[T3], T4],
        fn4: Callable[[T4], T5],
        fn5: Callable[[T5], T6],
        fn6: Callable[[T6], T7],
        fn7: Callable[[T7], T8],
        fn8: Callable[[T8], T9],
        /
) -> T9: ...


def flow(value: Any, /, *funcs: Callable[[Any], Any]) -> Any:
    result = value
    for fn in funcs:
        result = fn(result)
    return result

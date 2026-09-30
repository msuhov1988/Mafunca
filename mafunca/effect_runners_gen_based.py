from typing import TypeVar, overload, cast

from mafunca._lazy_support import ShortCircuitedError
from mafunca.result.build import Result, Success, Fail
from mafunca.eff.build import Eff, EffGenBased
from mafunca.eff_trans.build import EffResultGenBased
from mafunca.aff.build import Aff, AffGenBased
from mafunca.aff_trans.build import AffResultGenBased
from mafunca.effect_runners import run as classic_run, run_async as classic_run_async


__all__ = ["run", "run_safe", "run_async", "run_safe_async"]


A = TypeVar("A")
E = TypeVar("E")


def _sync_perform(eff: Eff[A]) -> Result[A, BaseException]:
    try:
        return Success(classic_run(eff))
    except BaseException as err:
        return Fail(err)


@overload
def run(effect_gen_based: EffResultGenBased[A, E]) -> Result[A, E]: ...

@overload
def run(effect_gen_based: EffGenBased[A]) -> A: ...

def run(effect_gen_based: EffResultGenBased[A, E] | EffGenBased[A]) -> Result[A, E] | A:
    """Simple synchronous executor - just runs a generator based effect"""
    gen = None
    try:
        gen = iter(effect_gen_based)
        try:
            eff = next(gen)
            while True:
                either = _sync_perform(eff)
                if isinstance(either, Fail):
                    eff = gen.throw(either.error)
                else:
                    output = either.value
                    break
        except ShortCircuitedError as err:            
            return cast(Result[A, E], err.fail)  # this error is thrown only by EffResultGenBased
        except StopIteration as err:
            if isinstance(effect_gen_based, EffResultGenBased):
                return cast(Result[A, E], Success(err.value))
            return cast(A, err.value)

        while True:
            try:
                eff = gen.send(output)
                while True:
                    either = _sync_perform(eff)
                    if isinstance(either, Fail):
                        eff = gen.throw(either.error)
                    else:
                        output = either.value
                        break 
            except ShortCircuitedError as err:                
                return cast(Result[A, E], err.fail)  # this error is thrown only by EffResultGenBased
            except StopIteration as err:
                if isinstance(effect_gen_based, EffResultGenBased):
                    return cast(Result[A, E], Success(err.value))
                return cast(A, err.value)
    finally:
        if gen is not None:
            gen.close()


@overload
def run_safe(effect_gen_based: EffResultGenBased[A, E]) -> Result[Result[A, E], Exception]: ...

@overload
def run_safe(effect_gen_based: EffGenBased[A]) -> Result[A, Exception]: ...

def run_safe(effect_gen_based: EffResultGenBased[A, E] | EffGenBased[A]) -> Result[Result[A, E] | A, Exception]:
    """
        Synchronous executor - runs a generator based effect, catching possible errors - heirs of ``Exception``
    """
    try:        
        return Success(run(effect_gen_based))
    except Exception as err:
        return Fail(err)


async def _async_perform(aff: Aff[A]) -> Result[A, BaseException]:
    try:
        return Success(await classic_run_async(aff))
    except BaseException as err:
        return Fail(err)


@overload
async def run_async(effect_gen_based: AffResultGenBased[A, E]) -> Result[A, E]: ...

@overload
async def run_async(effect_gen_based: AffGenBased[A]) -> A: ...

async def run_async(effect_gen_based: AffResultGenBased[A, E] | AffGenBased[A]) -> Result[A, E] | A:
    """Asynchronous executor - just runs a generator based effect"""
    gen = None
    try:
        gen = iter(effect_gen_based)
        try:
            aff = next(gen)
            while True:
                either = await _async_perform(aff)
                if isinstance(either, Fail):
                    aff = gen.throw(either.error)
                else:
                    output = either.value
                    break
        except ShortCircuitedError as err:            
            return cast(Result[A, E], err.fail)  # this error is thrown only by AffResultGenBased
        except StopIteration as err:
            if isinstance(effect_gen_based, AffResultGenBased):
                return cast(Result[A, E], Success(err.value))
            return cast(A, err.value)

        while True:
            try:
                aff = gen.send(output)
                while True:
                    either = await _async_perform(aff)
                    if isinstance(either, Fail):
                        aff = gen.throw(either.error)
                    else:
                        output = either.value
                        break
            except ShortCircuitedError as err:                
                return cast(Result[A, E], err.fail)  # this error is thrown only by AffResultGenBased
            except StopIteration as err:
                if isinstance(effect_gen_based, AffResultGenBased):
                    return cast(Result[A, E], Success(err.value))
                return cast(A, err.value)
    finally:
        if gen is not None:
            gen.close()


@overload
async def run_safe_async(effect_gen_based: AffResultGenBased[A, E]) -> Result[Result[A, E], Exception]: ...

@overload
async def run_safe_async(effect_gen_based: AffGenBased[A]) -> Result[A, Exception]: ...

async def run_safe_async(effect_gen_based: AffResultGenBased[A, E] | AffGenBased[A]) -> Result[Result[A, E] | A, Exception]:
    """
        Asynchronous executor - runs a generator based effect, catching possible errors - heirs of ``Exception``
    """
    try:        
        return Success(await run_async(effect_gen_based))
    except Exception as err:
        return Fail(err)

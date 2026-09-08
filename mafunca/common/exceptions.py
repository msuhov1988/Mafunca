from typing import TypeVar, Any


A = TypeVar("A")
B = TypeVar("B")


class MonadError(BaseException):
    """Thrown when monadic contracts are violated.
       Not recommended to import and catch.
       Separated - not in the error hierarchy of this library.
    """
    def __init__(self, monad: str, method: str, message: str):
        text = f"violation of the {monad} - {method} contract: {message}"
        super().__init__(text)


class MafuncaBaseError(Exception):
    """Base library level exception"""
    def __init__(self, message: str):
        super().__init__(message)


class CurryBadFunctionError(MafuncaBaseError):
    """Thrown when the 'curried' function is not suitable"""
    def __init__(self, func_name: str, err: str):
        text = f"{func_name} - {err}"
        super().__init__(text)


class CurryBadArguments(MafuncaBaseError):
    """thrown when the passed arguments for the function are incorrect"""
    def __init__(self, func_name: str, err: str):
        text = f"{func_name} - {err}"
        super().__init__(text)


class ValidationError(MafuncaBaseError):
    """An error thrown during validation of parameters"""
    def __init__(self, err: str):
        super().__init__(err)


class RetryByExceptionError(MafuncaBaseError):
    """An error is thrown when attempts are exhausted for nodes with retries"""
    def __init__(
            self,
            previous_result: Any,
            previous_result_is_assigned: bool,
            exception: Exception,
            step_name: str
    ):
        name = f" {step_name}" if step_name else ""
        super().__init__(f"Retryable step{name}: retry attempts exhausted by '{type(exception).__name__}'")
        self.previous_result = previous_result
        self.previous_result_is_assigned = previous_result_is_assigned
        self.exception = exception
        self.step_name = name


class RetryByValueError(MafuncaBaseError):
    """An error is thrown when attempts are exhausted for nodes with retries"""
    def __init__(
            self,
            previous_result: Any,
            previous_result_is_assigned: bool,
            current_result: Any,
            step_name: str
    ):
        name = f" {step_name}" if step_name else ""
        super().__init__(f"Retryable step{name}: retry attempts are exhausted due to the result predicate")
        self.previous_result = previous_result
        self.previous_result_is_assigned = previous_result_is_assigned
        self.current_result = current_result
        self.step_name = name


class RetryBadPauseError(MafuncaBaseError):
    """An error is thrown when there is an incorrect pause between attempts"""
    def __init__(self, step_name: str):
        name = f" {step_name}" if step_name else ""
        super().__init__(f"Retryable step{name}: delay must be a non-negative number")

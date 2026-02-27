class MonadError(Exception):
    """Thrown when monadic contracts are violated.
       Not recommended to import and catch.
       Separated - not in the error hierarchy of this library.
    """
    def __init__(self, monad: str, method: str, message: str):
        text = f"violation of the {monad}-{method} contract - {message}"
        super().__init__(text)


class BaseLibError(Exception):
    """Base library level exception"""
    def __init__(self, message: str):
        super().__init__(message)


class ImpureMarkError(BaseLibError):
    """Thrown when an attempt is made to mark a function as impure"""
    def __init__(self, func_name: str, err: str):
        text = f"Can't mark this function {func_name} as impure: {err}"
        super().__init__(text)


class CurryBadFunctionError(BaseLibError):
    """Thrown when the 'curried' function is not suitable"""
    def __init__(self, func_name: str, err: str):
        text = f"{func_name} - {err}"
        super().__init__(text)


class CurryBadArguments(BaseLibError):
    """thrown when the passed arguments for the function are incorrect"""
    def __init__(self, func_name: str, err: str):
        text = f"{func_name} - {err}"
        super().__init__(text)

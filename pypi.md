### Mafunca is a small FP library with a practical focus.
Rather than trying to implement every functional abstraction, it concentrates on a few useful ideas: 
- make failures explicit
- avoid scattering `None` checks across the codebase
- describe side effects lazily, so programs can be composed without performing them immediately 

The library is dependency-free and provides a stack-safe effect system with explicit execution, contract validation and
deliberately separate synchronous and asynchronous runtimes.

The effect system also supports composable error handling, scoped finalization and retry semantics.

Full documentation is available at the link: https://github.com/msuhov1988/Mafunca
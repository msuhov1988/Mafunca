### Mafunca is a small FP library with a practical focus.
Rather than trying to implement every functional abstraction, it concentrates on a few useful ideas: 
- make failures explicit
- avoid scattering `None` checks across the codebase
- describe side effects lazily, so functions remain pure while programs are being composed 

Mafunca is dependency-free, stack-safe in its effect system, strict about contracts and
deliberately keeps synchronous and asynchronous computations separate

Full documentation is available at the link: https://github.com/msuhov1988/Mafunca
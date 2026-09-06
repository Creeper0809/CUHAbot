"""Isolated Discord end-to-end runtime.

The Discord-dependent runtime is loaded lazily so the pure queue/result model
can be unit tested without importing the bot stack.
"""

__all__ = ["E2ERuntime"]


def __getattr__(name):
    if name == "E2ERuntime":
        from .runtime import E2ERuntime

        return E2ERuntime
    raise AttributeError(name)

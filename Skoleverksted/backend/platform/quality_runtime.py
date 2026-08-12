"""Runtime primitives for bounded, cancellable quality-gate work.

The quality gate is called from both worker threads and async FastAPI routes.
The provider SDK is synchronous, so a bounded daemon runner is used as a
second line of defence in addition to the provider's own HTTP timeout.
"""

from __future__ import annotations

import threading
import time
import os
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


class QualityLayerTimeout(TimeoutError):
    """The quality-layer budget or one model-call budget was exhausted."""


class QualityLayerCancelled(RuntimeError):
    """The owning generation job was cancelled by the user."""


def env_float(key: str, default: float, *, minimum: float = 0.1, maximum: float = 3600.0) -> float:
    try:
        value = float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def env_int(key: str, default: int, *, minimum: int = 1, maximum: int = 100) -> int:
    try:
        value = int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def run_bounded_sync(
    operation: Callable[[], T],
    *,
    timeout_seconds: float,
    cancel_check: Callable[[], bool] | None = None,
    operation_name: str = "quality operation",
) -> T:
    """Run a synchronous operation without blocking its caller forever.

    The underlying provider call also receives an SDK timeout.  The daemon
    thread here protects async callers and fake providers that do not honour
    that setting.  On cancellation/timeout the caller returns immediately;
    the provider client is closed by its owning wrapper in ``finally``.
    """
    if cancel_check and cancel_check():
        raise QualityLayerCancelled(f"{operation_name} cancelled")

    completed = threading.Event()
    result: list[T] = []
    error: list[BaseException] = []

    def invoke() -> None:
        try:
            result.append(operation())
        except BaseException as exc:  # propagate provider exceptions faithfully
            error.append(exc)
        finally:
            completed.set()

    thread = threading.Thread(
        target=invoke,
        daemon=True,
        name="quality-gate-call",
    )
    thread.start()
    deadline = time.monotonic() + max(0.01, timeout_seconds)
    while not completed.wait(timeout=min(0.05, max(0.0, deadline - time.monotonic()))):
        if cancel_check and cancel_check():
            raise QualityLayerCancelled(f"{operation_name} cancelled")
        if time.monotonic() >= deadline:
            raise QualityLayerTimeout(f"{operation_name} timed out")

    if cancel_check and cancel_check():
        raise QualityLayerCancelled(f"{operation_name} cancelled")
    if error:
        raise error[0]
    if not result:
        raise RuntimeError(f"{operation_name} returned no result")
    return result[0]

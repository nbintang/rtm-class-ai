from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rtm-job")


def queue_job(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
    return _executor.submit(func, *args, **kwargs)


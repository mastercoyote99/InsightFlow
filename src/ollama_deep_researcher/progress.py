"""Print heartbeat messages without starting additional model requests."""
from functools import wraps
from threading import Event, Thread
from time import perf_counter


def progress(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        stop = Event()
        start = perf_counter()
        print(f"[Started] {func.__name__}", flush=True)
        def heartbeat():
            while not stop.wait(15):
                print(f"[Waiting] {func.__name__}: {perf_counter()-start:.0f}s", flush=True)
        worker = Thread(target=heartbeat, daemon=True)
        worker.start()
        try:
            return func(*args, **kwargs)
        finally:
            stop.set()
            worker.join(timeout=1)
    return wrapped

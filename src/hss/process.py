import errno
import os
import signal
import subprocess
import time
from contextlib import contextmanager


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel and cancel():
        raise Cancelled("Preparation cancelled; completed resources are retained")


@contextmanager
def lock(path, *, blocking=True, cancel=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        acquired = False
        while not acquired:
            check_cancel(cancel)
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as error:
                if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                if not blocking:
                    break
                time.sleep(.1)
        try:
            yield acquired
        finally:
            if acquired:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)


def run(args, *, cancel=None, timeout=None, check=False, **kwargs):
    check_cancel(cancel)
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    if kwargs.pop("capture_output", False):
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        process = subprocess.Popen(args, **group, **kwargs)
    except FileNotFoundError:
        raise FileNotFoundError(f"Executable not found: {os.path.basename(args[0])}") from None
    with process:
        started = time.monotonic()
        try:
            while True:
                check_cancel(cancel)
                if timeout is not None and time.monotonic() - started >= timeout:
                    raise subprocess.TimeoutExpired(args, timeout)
                try:
                    stdout, stderr = process.communicate(timeout=.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.communicate()
            raise
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result

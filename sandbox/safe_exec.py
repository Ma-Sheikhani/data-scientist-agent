import base64
import builtins
import io
import multiprocessing
import os
import sys
import tempfile
import traceback
from typing import Any, Dict

# Whitelist of allowed modules
ALLOWED_MODULES = {
    "pandas",
    "numpy",
    "matplotlib",
    "sklearn",
    "scipy",
    "json",
    "math",
    "statistics",
    "random",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "operator",
    "typing",
    "re",
    "string",
    "copy",
    "warnings",
}


def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Allow import if the top-level package is in the whitelist."""
    top_level = name.split(".")[0]
    if top_level not in ALLOWED_MODULES:
        raise ImportError(f"Module '{name}' is not allowed")
    return __import__(name, globals, locals, fromlist, level)


def restricted_open(file, mode="r", *args, **kwargs):
    """Allow file operations only within the current working directory."""
    # For simplicity, we trust that the working directory is isolated.
    # But we can also block any absolute paths outside.
    if os.path.isabs(file):
        # Only allow if it's inside the cwd (we'll set cwd to a temp dir)
        cwd = os.getcwd()
        if not os.path.abspath(file).startswith(cwd):
            raise IOError("Access denied")
    return open(file, mode, *args, **kwargs)


def execute_code(code: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Run Python code in a separate process with restricted builtins,
    capture stdout/stderr, collect .png images from the working directory.
    Returns dict with stdout, stderr, error, images (list of base64).
    """
    # Create a temporary directory to run the code in
    with tempfile.TemporaryDirectory() as tmpdir:
        # Change to that directory
        os.chdir(tmpdir)

        # Prepare a dict of builtins to pass to the subprocess
        safe_builtins = {
            # Exclude dangerous builtins
            "print": builtins.print,
            "len": builtins.len,
            "range": builtins.range,
            "int": builtins.int,
            "float": builtins.float,
            "str": builtins.str,
            "list": builtins.list,
            "dict": builtins.dict,
            "set": builtins.set,
            "tuple": builtins.tuple,
            "bool": builtins.bool,
            "abs": builtins.abs,
            "all": builtins.all,
            "any": builtins.any,
            "divmod": builtins.divmod,
            "enumerate": builtins.enumerate,
            "filter": builtins.filter,
            "map": builtins.map,
            "max": builtins.max,
            "min": builtins.min,
            "pow": builtins.pow,
            "round": builtins.round,
            "sorted": builtins.sorted,
            "sum": builtins.sum,
            "zip": builtins.zip,
            "isinstance": builtins.isinstance,
            "type": builtins.type,
            "Exception": Exception,
        }
        # We'll also inject our restricted import and open
        safe_builtins["__import__"] = restricted_import
        safe_builtins["open"] = restricted_open

        # Capture stdout/stderr
        out_queue: multiprocessing.Queue[str] = multiprocessing.Queue()
        err_queue: multiprocessing.Queue[str] = multiprocessing.Queue()

        def target():
            # Redirect stdout/stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            try:
                exec(code, {"__builtins__": safe_builtins})  # nosec B102
            except Exception:
                # Put the traceback in stderr
                sys.stderr.write(traceback.format_exc())
            finally:
                out_queue.put(sys.stdout.getvalue())
                err_queue.put(sys.stderr.getvalue())

        proc = multiprocessing.Process(target=target)
        proc.start()
        proc.join(timeout)

        if proc.is_alive():
            proc.terminate()
            proc.join()
            return {
                "stdout": "",
                "stderr": "",
                "error": "Code execution timed out",
                "images": [],
            }

        stdout = out_queue.get() if not out_queue.empty() else ""
        stderr = err_queue.get() if not err_queue.empty() else ""
        error = None

        # Collect any .png files saved in the working directory
        images = []
        for fname in os.listdir(tmpdir):
            if fname.endswith(".png"):
                with open(os.path.join(tmpdir, fname), "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                    images.append(b64)

        return {
            "stdout": stdout,
            "stderr": stderr,
            "error": error,
            "images": images,
        }

"""Local-only historical Git checkout for immutable release evidence."""
from contextlib import contextmanager
from pathlib import Path
import subprocess
import tempfile


@contextmanager
def historical_checkout(repository, commit):
    with tempfile.TemporaryDirectory(prefix="mosa2-historical-release-") as temporary:
        parent = Path(temporary).resolve()
        checkout = parent / "checkout"
        assert checkout.resolve().parent == parent
        subprocess.run(["git", "clone", "--quiet", "--local", "--no-hardlinks",
                        "--no-checkout", str(Path(repository).resolve()), str(checkout)], check=True)
        subprocess.run(["git", "-C", str(checkout), "-c", "core.autocrlf=false",
                        "checkout", "--quiet", "--detach", commit], check=True)
        yield checkout

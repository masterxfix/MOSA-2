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


@contextmanager
def candidate_checkout(repository, commit, paths):
    """Commit pending text changes only inside the existing isolated test checkout."""
    with historical_checkout(repository, commit) as checkout:
        for path in paths:
            target = checkout/path
            assert target.resolve().is_relative_to(checkout)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Match Git's canonical text bytes, not a Windows CRLF worktree.
            target.write_bytes((Path(repository)/path).read_bytes().replace(b"\r\n", b"\n"))
        subprocess.run(["git", "-C", str(checkout), "-c", "core.autocrlf=false", "add", "--", *paths], check=True)
        subprocess.run(["git", "-C", str(checkout), "-c", "user.name=MOSA offline fixture",
                        "-c", "user.email=offline@example.invalid", "-c", "commit.gpgsign=false",
                        "commit", "--quiet", "-m", "Synthetic offline candidate"], check=True)
        identity = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        yield checkout, identity

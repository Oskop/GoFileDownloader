"""Module to handle common tasks and environment detection."""

from __future__ import annotations

import os
import subprocess
import sys


def is_colab() -> bool:
    """Check if running in Google Colab environment."""
    return (
        "google.colab" in sys.modules
        or os.environ.get("COLAB_RELEASE_TAG") is not None
        or os.environ.get("COLAB_GPU") is not None
    )


def is_jupyter() -> bool:
    """Check if running inside a Jupyter/IPython environment."""
    try:
        from IPython import get_ipython  # type: ignore

        return get_ipython() is not None
    except ImportError:
        return False


def is_interactive_terminal() -> bool:
    """Check if standard output is attached to an interactive terminal (TTY)."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def should_use_simple_progress() -> bool:
    """Determine whether simple single-line progress should be enabled by default."""
    return is_colab() or is_jupyter() or not is_interactive_terminal()


def clear_terminal() -> None:
    """Clear the terminal screen or notebook output cell."""
    if is_colab() or is_jupyter():
        try:
            from IPython.display import clear_output  # type: ignore

            clear_output(wait=True)
            return
        except ImportError:
            pass

    commands = {
        "nt": "cls",       # Windows
        "posix": "clear",  # macOS and Linux
    }

    command = commands.get(os.name)
    if command:
        try:
            subprocess.run(command, shell=True, check=True)  # noqa: S603
        except Exception:
            pass


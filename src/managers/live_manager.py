"""Module that provides functionality for managing and displaying live updates.

It combines a progress table and a logger table into a real-time display, allowing
dynamic updates of both tables. The `LiveManager` class handles the integration and
refresh of the live view, supporting both standard multi-line terminal UI and simple
single-line progress for Google Colab and non-TTY environments.
"""

from __future__ import annotations

import datetime
import sys
import threading
import time
from contextlib import nullcontext
from typing import TYPE_CHECKING

from rich.align import Align
from rich.console import Group
from rich.live import Live
from rich.text import Text

from src.general_utils import should_use_simple_progress
from src.version import get_version_string

from .log_manager import LoggerTable
from .progress_manager import ProgressManager

if TYPE_CHECKING:
    from argparse import Namespace


class LiveManager:
    """Class to manage a live display that combines a progress table and a logger table.

    It allows for real-time updates and refreshes of both progress and logs in a
    terminal, with automatic fallback to single-line progress for Google Colab/non-TTY.
    """

    def __init__(
        self,
        progress_manager: ProgressManager,
        logger_table: LoggerTable,
        refresh_per_second: int = 10,
        *,
        simple_mode: bool = False,
    ) -> None:
        """Initialize the progress manager and logger, and set up the live view."""
        self.progress_manager = progress_manager
        self.logger_table = logger_table
        self.simple_mode = simple_mode
        self.start_time = time.time()

        self._lock = threading.Lock()
        self._last_line_len = 0
        self._current_album = ""
        self._num_tasks = 0
        self._task_info: dict[int, int] = {}

        if not self.simple_mode:
            self.progress_table = self.progress_manager.create_progress_table()
            self.live = Live(
                self._render_live_view(), refresh_per_second=refresh_per_second,
            )
        else:
            self.progress_table = None
            self.live = nullcontext()

        self.update_log(
            event="Script started",
            details="The script has started execution.",
        )

    def add_overall_task(self, description: str, num_tasks: int) -> None:
        """Add an overall progress task."""
        self._current_album = description
        self._num_tasks = num_tasks
        self.progress_manager.add_overall_task(description, num_tasks)

        if self.simple_mode:
            self.update_log(
                event="Started Album",
                details=f"{description} ({num_tasks} files)",
            )

    def add_task(self, current_task: int = 0, total: int = 100) -> int:
        """Add an individual task to the progress tracking."""
        task_id = self.progress_manager.add_task(current_task, total)
        self._task_info[task_id] = current_task + 1
        return task_id

    def update_task(
        self,
        task_id: int,
        completed: int | None = None,
        advance: int = 0,
        *,
        visible: bool = True,
    ) -> None:
        """Update an individual task and overall progress."""
        self.progress_manager.update_task(task_id, completed, advance, visible=visible)

        if self.simple_mode and completed is not None:
            with self._lock:
                task_idx = self._task_info.get(task_id, task_id + 1)
                if completed >= 100:
                    if self._last_line_len > 0:
                        sys.stdout.write("\r" + " " * self._last_line_len + "\r")
                        self._last_line_len = 0
                    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
                    print(
                        f"[{timestamp}] [Completed] {self.progress_manager.config.item_description} "
                        f"{task_idx}/{self._num_tasks}",
                        flush=True,
                    )
                else:
                    percentage = max(0.0, min(100.0, completed))
                    bar_width = 20
                    filled = int(bar_width * percentage / 100)
                    bar = "=" * filled + (">" if filled < bar_width else "")
                    bar = bar.ljust(bar_width, " ")
                    line = (
                        f"[Album: {self._current_album}] "
                        f"[{self.progress_manager.config.item_description} {task_idx}/{self._num_tasks}] "
                        f"[{bar}] {percentage:5.1f}%"
                    )
                    sys.stdout.write(f"\r{line.ljust(self._last_line_len)}")
                    self._last_line_len = max(len(line), self._last_line_len)
                    sys.stdout.flush()

    def update_log(self, *, event: str, details: str) -> None:
        """Log an event and refresh the display."""
        if not self.simple_mode:
            self.logger_table.log(event, details)
            self.live.update(self._render_live_view())
        else:
            with self._lock:
                if self._last_line_len > 0:
                    sys.stdout.write("\r" + " " * self._last_line_len + "\r")
                    self._last_line_len = 0
                timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
                print(f"[{timestamp}] [{event}] {details}", flush=True)

    def start(self) -> None:
        """Start the live display."""
        if not self.simple_mode:
            self.live.start()

    def stop(self) -> None:
        """Stop the live display and log execution time."""
        if self.simple_mode:
            with self._lock:
                if self._last_line_len > 0:
                    sys.stdout.write("\r" + " " * self._last_line_len + "\r")
                    self._last_line_len = 0

        execution_time = self._compute_execution_time()
        self.update_log(
            event="Script ended",
            details=f"The script has finished execution. Execution time: {execution_time}",
        )

        if not self.simple_mode:
            self.live.stop()

    def __enter__(self) -> LiveManager:
        """Enter the context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: object | None) -> None:
        """Exit the context manager."""
        self.stop()

    # Private methods
    def _render_live_view(self) -> Group:
        """Render the combined live view of the progress table and the logger table."""
        panel_width = self.progress_manager.get_panel_width()
        footer_text = Text(get_version_string(), style="dim")
        footer = Align.left(footer_text)
        return Group(
            self.progress_table,
            self.logger_table.render_log_panel(panel_width=2 * panel_width),
            footer,
        )

    def _compute_execution_time(self) -> str:
        """Compute and format the execution time of the script."""
        execution_time = time.time() - self.start_time
        time_delta = datetime.timedelta(seconds=execution_time)

        # Extract hours, minutes, and seconds from the timedelta object
        hours = time_delta.seconds // 3600
        minutes = (time_delta.seconds % 3600) // 60
        seconds = time_delta.seconds % 60
        return f"{hours:02} hrs {minutes:02} mins {seconds:02} secs"


def initialize_managers(
    args: Namespace | None = None,
    *,
    simple_mode: bool | None = None,
) -> LiveManager:
    """Initialize and returns the managers for progress tracking and logging."""
    if simple_mode is None:
        if args is not None and getattr(args, "simple_progress", False):
            simple_mode = True
        else:
            simple_mode = should_use_simple_progress()

    progress_manager = ProgressManager(task_name="Album", item_description="File")
    logger_table = LoggerTable()
    return LiveManager(progress_manager, logger_table, simple_mode=simple_mode)


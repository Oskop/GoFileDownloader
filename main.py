"""Main module of the project.

Usage:
    Ensure that a file named 'URLs.txt' is present in the same directory as this script.
    The file should contain a list of URLs, one per line. When executed, the script
    will:
        1. Read the URLs from 'URLs.txt'.
        2. Process each URL for downloading anime content.
        3. Clear the contents of 'URLs.txt' after all URLs have been processed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from downloader import handle_download_process
from src.config import SESSION_LOG, URLS_FILE, parse_arguments
from src.file_utils import read_file, write_file
from src.general_utils import clear_terminal
from src.managers.live_manager import initialize_managers

if TYPE_CHECKING:
    from argparse import Namespace

URLS_FILE_PATH = Path.cwd() / URLS_FILE
SESSION_FILE_PATH = Path.cwd() / SESSION_LOG


def process_urls(urls: list[str], args: Namespace | None = None) -> None:
    """Validate and downloads items for a list of URLs."""
    live_manager = initialize_managers()

    try:
        with live_manager.live:
            for url in urls:
                handle_download_process(url, live_manager, args=args)

            live_manager.stop()

    except KeyboardInterrupt:
        sys.exit(1)


def main() -> None:
    """Run the script."""
    # Clear the terminal and session log file
    clear_terminal()
    write_file(SESSION_FILE_PATH)

    # Parse arguments
    args = parse_arguments(common_only=True)

    # Read and process URLs, ignoring empty lines
    urls = [url.strip() for url in read_file(URLS_FILE_PATH) if url.strip()]
    process_urls(urls, args)

    # Clear URLs file
    write_file(URLS_FILE_PATH)


if __name__ == "__main__":
    main()

import argparse
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import web_to_cookbook as wtc


def process_file(file_path: Path, target_folder: Path, interface: str = "") -> None:
    """Process a file that contains either a URL or raw HTML.

    If the file text contains ``<html`` it is treated as HTML and passed to
    :class:`web_to_cookbook.HTMLToCookbook`. Otherwise the content is assumed to
    be a URL and handled by :class:`web_to_cookbook.URLToCookbook`.
    """
    text = file_path.read_text(encoding="utf-8").strip()
    if "<html" in text.lower():
        parser = wtc.HTMLToCookbook(html_list=[text], target_folder=target_folder, interface=interface)
        parser.run_through_htmls()
    else:
        parser = wtc.URLToCookbook(url_list=[text], target_folder=target_folder, interface=interface)
        parser.run_through_urls()


class RecipeFileHandler(FileSystemEventHandler):
    """Event handler that triggers recipe parsing on new files."""

    def __init__(self, target_folder: Path, interface: str = "") -> None:
        self.target_folder = target_folder
        self.interface = interface

    def on_created(self, event):  # type: ignore[override]
        if event.is_directory:
            return
        process_file(Path(event.src_path), self.target_folder, self.interface)


def watch_directory(source: Path, target: Path, interface: str = "") -> Observer:
    """Start watching *source* for new files and process them.

    Returns the :class:`watchdog.observers.Observer` instance so callers can
    manage its lifecycle (useful for tests).
    """
    handler = RecipeFileHandler(target, interface)
    observer = Observer()
    observer.schedule(handler, str(source), recursive=False)
    observer.start()
    return observer


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch a folder for recipe files and parse them")
    parser.add_argument("source", type=Path, help="Folder to watch for new files")
    parser.add_argument("target", type=Path, help="Folder to store parsed recipes")
    parser.add_argument("-i", "--interface", default="", help="Network interface to use")
    args = parser.parse_args()

    observer = watch_directory(args.source, args.target, args.interface)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()

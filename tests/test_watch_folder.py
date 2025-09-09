import time

import watch_folder
import web_to_cookbook as wtc


def test_process_file_url(tmp_path, monkeypatch):
    called = {}

    class DummyURL:
        def __init__(self, url_list, target_folder, interface=""):
            called["url_list"] = url_list

        def run_through_urls(self):
            called["run"] = True

    monkeypatch.setattr(wtc, "URLToCookbook", DummyURL)

    file_path = tmp_path / "url.txt"
    file_path.write_text("http://example.com")

    watch_folder.process_file(file_path, tmp_path)

    assert called["url_list"] == ["http://example.com"]
    assert called["run"]


def test_process_file_html(tmp_path, monkeypatch):
    called = {}

    class DummyHTML:
        def __init__(self, html_list, target_folder, interface=""):
            called["html_list"] = html_list

        def run_through_htmls(self):
            called["run"] = True

    monkeypatch.setattr(wtc, "HTMLToCookbook", DummyHTML)

    file_path = tmp_path / "page.html"
    file_path.write_text("<html><body>Hi</body></html>")

    watch_folder.process_file(file_path, tmp_path)

    assert "<html>" in called["html_list"][0]
    assert called["run"]


def test_watch_directory(tmp_path, monkeypatch):
    called = {}

    class DummyURL:
        def __init__(self, url_list, target_folder, interface=""):
            called["url_list"] = url_list

        def run_through_urls(self):
            called["run"] = True

    monkeypatch.setattr(wtc, "URLToCookbook", DummyURL)

    watch_dir = tmp_path / "incoming"
    watch_dir.mkdir()
    target = tmp_path / "out"
    target.mkdir()

    observer = watch_folder.watch_directory(watch_dir, target)

    try:
        file_path = watch_dir / "url.txt"
        file_path.write_text("http://example.com")
        # wait for the observer to pick up the event
        for _ in range(10):
            if called.get("run"):
                break
            time.sleep(0.2)
        assert called["url_list"] == ["http://example.com"]
        assert called["run"]
    finally:
        observer.stop()
        observer.join()

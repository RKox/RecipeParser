import io
import pickle
import runpy
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import web_to_cookbook as wtc


# -------- get_source_ip ---------

def test_get_source_ip_variants(monkeypatch):
    # default with empty interface
    assert wtc.get_source_ip("") == "127.0.0.1"

    # valid interface with IPv4 address
    monkeypatch.setattr(wtc.netifaces, "interfaces", lambda: ["eth0"])
    monkeypatch.setattr(
        wtc.netifaces,
        "ifaddresses",
        lambda iface: {wtc.netifaces.AF_INET: [{"addr": "1.2.3.4"}]},
    )
    assert wtc.get_source_ip("eth0") == "1.2.3.4"

    # interface not found
    monkeypatch.setattr(wtc.netifaces, "interfaces", lambda: ["eth0"])
    with pytest.raises(ValueError):
        wtc.get_source_ip("wlan0")

    # interface without IPv4
    monkeypatch.setattr(wtc.netifaces, "interfaces", lambda: ["lo"])
    monkeypatch.setattr(wtc.netifaces, "ifaddresses", lambda iface: {})
    with pytest.raises(ValueError):
        wtc.get_source_ip("lo")


# -------- _get_new_session ---------

def test_get_new_session_uses_cookiejar(tmp_path, monkeypatch):
    cookie_file = tmp_path / "cookies.pkl"
    with cookie_file.open("wb") as f:
        pickle.dump({"existing": "cookie"}, f)
    monkeypatch.setattr(wtc, "COOKIEJAR", cookie_file)

    class DummySession:
        def __init__(self):
            from requests.cookies import RequestsCookieJar

            self.cookies = RequestsCookieJar()
        def mount(self, *a, **k):
            pass
        def close(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            self.close()
    monkeypatch.setattr(wtc, "HTMLSession", DummySession)
    monkeypatch.setattr(wtc, "get_source_ip", lambda interface="": "127.0.0.1")

    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    with obj._get_new_session() as session:
        assert session.cookies.get("existing") == "cookie"
        session.cookies.set("new", "value")
    with cookie_file.open("rb") as f:
        saved = pickle.load(f)
    assert saved["new"] == "value"


def test_get_new_session_creates_cookiejar(tmp_path, monkeypatch):
    cookie_file = tmp_path / "cookies.pkl"
    monkeypatch.setattr(wtc, "COOKIEJAR", cookie_file)

    class DummySession:
        def __init__(self):
            from requests.cookies import RequestsCookieJar
            self.cookies = RequestsCookieJar()
        def mount(self, *a, **k):
            pass
        def close(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            self.close()
    monkeypatch.setattr(wtc, "HTMLSession", DummySession)
    monkeypatch.setattr(wtc, "get_source_ip", lambda interface="": "127.0.0.1")

    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    with obj._get_new_session():
        pass
    assert cookie_file.exists()


# -------- __init__ folder creation / properties ---------

def test_init_creates_folder_and_properties(tmp_path):
    target = tmp_path / "newfolder"
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=target)
    assert target.exists()
    assert obj.success_recipes == []
    assert [c for c in obj.not_success_recipes if c.source is wtc.Source.url]


# -------- _html_to_recipe ---------

def test_html_to_recipe_extracts_url(monkeypatch):
    html = "<a href='http://example.com/r'></a>"
    dummy_recipe = Mock()
    monkeypatch.setattr(wtc, "HTML", lambda html: SimpleNamespace(links=["http://example.com/r"]))
    monkeypatch.setattr(wtc, "scrape_html", lambda html, org_url, supported_only: dummy_recipe)
    recipe = wtc.HTMLToCookbook._html_to_recipe(html=html, url="")
    assert recipe is dummy_recipe


# -------- _get_and_save_image & _save_to_json ---------

def test_save_image_and_json(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    container = wtc.RecipeContainer(source=wtc.Source.html, source_content="")
    recipe = wtc.RecipeForCookBook(name="Soup", recipeYield=1, image="http://img")
    container.parsed_recipe = recipe
    container.target_folder = tmp_path / "soup"
    container.target_folder.mkdir()

    @contextmanager
    def fake_session():
        class _S:
            def get(self, url):
                return SimpleNamespace(content=b"imgdata")
            def mount(self, *a, **k):
                pass
            @property
            def cookies(self):
                from requests.cookies import RequestsCookieJar
                return RequestsCookieJar()
        yield _S()
    monkeypatch.setattr(obj, "_get_new_session", fake_session)

    img_path = obj._get_and_save_image(container)
    assert img_path.exists()

    json_path = obj._save_to_json(container)
    assert json_path.exists()
    assert "Soup" in json_path.read_text()


# -------- _save_scraped_recipe ---------

def test_save_scraped_recipe_flow(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    container = wtc.RecipeContainer(source=wtc.Source.html, source_content="")
    container.raw_recipe = Mock()
    recipe = wtc.RecipeForCookBook(name="Salad", recipeYield=1, image="http://img")
    monkeypatch.setattr(wtc, "parse_recipe", lambda recipe: recipe)
    container.raw_recipe = recipe
    def fake_create(recipe_container):
        path = tmp_path / "salad"
        path.mkdir()
        return path
    monkeypatch.setattr(obj, "_create_target_folder", fake_create)
    monkeypatch.setattr(obj, "_get_and_save_image", lambda recipe_container: None)
    obj._save_scraped_recipe(container)
    assert container.parsed_recipe is recipe
    assert (tmp_path / "salad" / wtc.RECIPE_FILENAME).exists()


# -------- html_to_cookbook ---------

def test_html_to_cookbook_calls_helpers(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    container = wtc.RecipeContainer(source=wtc.Source.html, source_content="<html></html>")
    monkeypatch.setattr(obj, "_html_to_recipe", lambda html, supported_only=False: "RAW")
    called = {}
    monkeypatch.setattr(obj, "_save_scraped_recipe", lambda recipe_container: called.setdefault("saved", True))
    obj.html_to_cookbook(container)
    assert called["saved"]
    assert container.raw_recipe == "RAW"


# -------- _create_target_folder ---------

def test_create_target_folder_handles_duplicates(tmp_path):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    r1 = wtc.RecipeForCookBook(name="Cake", recipeYield=1)
    c1 = wtc.RecipeContainer(source=wtc.Source.html, source_content="")
    c1.parsed_recipe = r1
    path1 = obj._create_target_folder(c1)
    assert path1.exists()
    r2 = wtc.RecipeForCookBook(name="Cake", recipeYield=1)
    c2 = wtc.RecipeContainer(source=wtc.Source.html, source_content="")
    c2.parsed_recipe = r2
    path2 = obj._create_target_folder(c2)
    assert path2.name.endswith("_2")


# -------- _get_recipe_from_url ---------

def test_get_recipe_from_url(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    container = wtc.RecipeContainer(source=wtc.Source.url, source_content="http://a")
    monkeypatch.setattr(obj, "_get_html_from_url", lambda url: "<html></html>")
    monkeypatch.setattr(obj, "_html_to_recipe", lambda html, url: "RECIPE")
    result = obj._get_recipe_from_url(container)
    assert result == "RECIPE"
    assert container.raw_recipe == "RECIPE"


# -------- _get_html_from_url success path ---------

def test_get_html_from_url_success(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    monkeypatch.setattr(wtc, "get_proper_parser", lambda url: type("P", (), {"HEADERS": {}}))

    class Resp:
        status_code = 200
        content = b"html"
        def raise_for_status(self):
            return None
    @contextmanager
    def fake_session():
        class S:
            def get(self, url, headers=None, allow_redirects=False):
                return Resp()
            def mount(self, *a, **k):
                pass
            @property
            def cookies(self):
                from requests.cookies import RequestsCookieJar
                return RequestsCookieJar()
        yield S()
    monkeypatch.setattr(obj, "_get_new_session", fake_session)
    html = obj._get_html_from_url("http://example.com")
    assert html == "html"


def test_get_html_from_url_http_error(tmp_path, monkeypatch):
    from requests import HTTPError
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    monkeypatch.setattr(wtc, "get_proper_parser", lambda url: type("P", (), {"HEADERS": {}}))
    class Resp:
        status_code = 500
        content = b""
        def raise_for_status(self):
            raise HTTPError(response=self)
    @contextmanager
    def fake_session():
        class S:
            def get(self, url, headers=None, allow_redirects=False):
                return Resp()
            def mount(self, *a, **k):
                pass
            @property
            def cookies(self):
                from requests.cookies import RequestsCookieJar
                return RequestsCookieJar()
        yield S()
    monkeypatch.setattr(obj, "_get_new_session", fake_session)
    with pytest.raises(HTTPError):
        obj._get_html_from_url("http://example.com")


# -------- web_to_cookbook success and failure ---------

def test_web_to_cookbook_success(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    container = wtc.RecipeContainer(source=wtc.Source.url, source_content="http://a")
    monkeypatch.setattr(obj, "_get_recipe_from_url", lambda recipe_container: None)
    monkeypatch.setattr(obj, "_save_scraped_recipe", lambda recipe_container: None)
    obj.web_to_cookbook(container)
    assert container.success


def test_web_to_cookbook_failure_cleans(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    container = wtc.RecipeContainer(source=wtc.Source.url, source_content="bad")
    container.target_folder = tmp_path / "bad"
    container.target_folder.mkdir()
    monkeypatch.setattr(obj, "_get_recipe_from_url", lambda recipe_container: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        obj.web_to_cookbook(container)
    assert not container.target_folder.exists()


# -------- run_through_htmls ---------

def test_run_through_htmls_collects_exceptions(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], html_list=["<h>"] , target_folder=tmp_path)
    failing = wtc.RecipeContainer(source=wtc.Source.html, source_content="bad")
    obj._source_recipes.add(failing)
    def side_effect(recipe_container):
        if recipe_container.source_content == "bad":
            raise ValueError("boom")
        recipe_container.success = True
    monkeypatch.setattr(obj, "html_to_cookbook", side_effect)
    with pytest.raises(ExceptionGroup):
        obj.run_through_htmls()
    assert any(r.success for r in obj._source_recipes)


# -------- run_through_urls ---------

def test_run_through_urls_collects_exceptions(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://good", "http://bad"], target_folder=tmp_path)
    # include non-url container to hit continue
    obj._source_recipes.add(wtc.RecipeContainer(source=wtc.Source.html, source_content="ignored"))

    def side_effect(recipe_container):
        if recipe_container.source_content.endswith("bad"):
            raise ValueError("fail")
        recipe_container.success = True
    monkeypatch.setattr(obj, "web_to_cookbook", side_effect)
    called = []
    monkeypatch.setattr(obj, "_update_failed_urls_file", lambda file_path: called.append(file_path))
    with pytest.raises(ExceptionGroup):
        obj.run_through_urls()
    assert called and len(called) == 1
    assert any(c.success for c in obj._source_recipes)


# -------- run_through_urls_with_retry ---------

def test_run_through_urls_with_retry(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    container = next(iter(obj._source_recipes))
    attempts = {"n": 0}
    def fake_run():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ExceptionGroup("e", [Exception("boom")])
        container.success = True
    monkeypatch.setattr(obj, "run_through_urls", fake_run)
    monkeypatch.setattr(wtc.time, "sleep", lambda x: None)
    obj.run_through_urls_with_retry(retries=2)
    assert attempts["n"] == 2
    assert container.success


def test_run_through_urls_with_retry_fail(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://a"], target_folder=tmp_path)
    monkeypatch.setattr(
        obj,
        "run_through_urls",
        lambda: (_ for _ in ()).throw(ExceptionGroup("e", [Exception("boom")]))
    )
    monkeypatch.setattr(wtc.time, "sleep", lambda x: None)
    obj.run_through_urls_with_retry(retries=1)
    assert not next(iter(obj._source_recipes)).success


def test_main_block_executes(tmp_path, monkeypatch):
    import argparse
    import textwrap
    source = Path(wtc.__file__).read_text().splitlines()
    start = source.index('if __name__ == "__main__":') + 1
    main_code = textwrap.dedent("\n".join(source[start:]))

    html_file = tmp_path / "h.html"
    html_file.write_text("<!DOCTYPE html>")
    url_file = tmp_path / "u.txt"
    url_file.write_text("http://a")

    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda self: argparse.Namespace(interface="", url=[], file=[str(html_file), str(url_file)], target=str(tmp_path / "out")),
    )

    class DummyURLToCookbook:
        def __init__(self, url_list, html_list, target_folder, interface):
            self.url_list = url_list
            self.html_list = html_list
        def run_through_urls_with_retry(self, retries):
            pass
        def run_through_htmls(self):
            pass

    monkeypatch.setattr(wtc, "URLToCookbook", DummyURLToCookbook)
    monkeypatch.setattr(wtc, "get_urls_from_file", lambda url_file: ["http://fromfile"])

    exec(compile("\n" * start + main_code, wtc.__file__, "exec"), wtc.__dict__)
    assert not html_file.exists() and not url_file.exists()


# -------- _update_failed_urls_file ---------

def test_update_failed_urls_file(tmp_path, monkeypatch):
    obj = wtc.URLToCookbook(url_list=["http://good", "http://bad"], target_folder=tmp_path)
    containers = {c.source_content: c for c in obj._source_recipes}
    containers["http://good"].success = True
    file_path = tmp_path / "failed.txt"
    file_path.write_text("http://old\nhttp://good")
    class Extractor:
        def find_urls(self, text):
            return [u for u in text.split() if u.startswith("http")]
    monkeypatch.setattr(wtc, "URLExtract", lambda: Extractor())
    obj._update_failed_urls_file(file_path)
    out = file_path.read_text().splitlines()
    assert "http://old" in out and "http://bad" in out and "http://good" not in out


# -------- get_urls_from_file ---------

def test_get_urls_from_file(tmp_path, monkeypatch):
    file = tmp_path / "urls.txt"
    file.write_text("one http://a.com two http://b.com")
    class Extractor:
        def find_urls(self, text):
            return [u for u in text.split() if u.startswith("http")]
    monkeypatch.setattr(wtc, "URLExtract", lambda: Extractor())
    urls = wtc.get_urls_from_file(file)
    assert urls == ["http://a.com", "http://b.com"]

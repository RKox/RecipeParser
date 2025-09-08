import pytest
from unittest.mock import patch, MagicMock
from web_to_cookbook import URLToCookbook
from pathlib import Path


@patch("web_to_cookbook.get_proper_parser")
@patch("web_to_cookbook.requests.Session.get")
def test_fallback_to_curl_on_403(mock_get, mock_parser, tmp_path: Path):
    """Simulate 403 from requests and ensure curl_cffi path is exercised."""
    # Parser headers not important for test – return empty dict.
    class _P:
        HEADERS = {}
    mock_parser.return_value = _P

    # First call returns a response that raises for status with 403.
    resp = MagicMock()
    resp.status_code = 403
    def _raise():
        from requests import HTTPError
        raise HTTPError(response=resp)
    resp.raise_for_status.side_effect = _raise
    mock_get.return_value = resp

    # Patch curl_cffi.requests.get to return OK text.
    with patch("web_to_cookbook.curl_requests") as curl_mod:
        ok = MagicMock()
        ok.text = "<html>ok</html>"
        ok.raise_for_status.return_value = None
        curl_mod.get.return_value = ok

        u = URLToCookbook(url_list=["https://www.ah.nl/r/1199850"], target_folder=tmp_path)
        html = u._get_html_from_url("https://www.ah.nl/r/1199850")
        assert "ok" in html

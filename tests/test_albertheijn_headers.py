import pytest
from parsers import get_proper_parser, AlbertHeijnRecipeParser, DefaultRecipeParser


def test_ahnl_parser_selected():
    cls = get_proper_parser("https://www.ah.nl/r/1199850")
    assert cls is AlbertHeijnRecipeParser


def test_default_parser_selected_for_unknown():
    cls = get_proper_parser("https://example.com/something")
    assert cls is DefaultRecipeParser


def test_ahnl_headers_look_browserlike():
    headers = AlbertHeijnRecipeParser.HEADERS
    assert "User-Agent" in headers
    assert "Accept-Language" in headers
    assert "Accept-Encoding" in headers

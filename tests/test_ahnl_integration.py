import pytest
import requests
from recipe_scrapers import scrape_html

from parsers import AlbertHeijnRecipeParser

AH_URL = "https://www.ah.nl/allerhande/recept/R-R1196840"


@pytest.mark.integration
def test_ahnl_requires_browser_headers():
    """The Albert Heijn site blocks plain requests with a 403.
    Using the browser-like headers defined in the parser should
    allow us to fetch the recipe HTML and parse the title."""

    r_forbidden = requests.get(AH_URL)
    assert r_forbidden.status_code == 403

    r_ok = requests.get(AH_URL, headers=AlbertHeijnRecipeParser.HEADERS)
    r_ok.raise_for_status()

    recipe = scrape_html(html=r_ok.text, org_url=r_ok.url, supported_only=False)
    assert "spanakopita" in recipe.title().lower()

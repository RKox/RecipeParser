import pytest
from unittest.mock import Mock
from types import SimpleNamespace

import parsers
from parsers import (
    RecipeForCookBook,
    DefaultRecipeParser,
    get_proper_parser,
    AlbertHeijnRecipeParser,
)


def test_recipe_to_json_and_folder_name():
    recipe = RecipeForCookBook(name="A/B Test", recipeYield=2, author="", description="")
    data = recipe.to_json()
    # Empty author/description should be removed
    assert "author" not in data
    assert data["name"] == "A/B Test"
    # Schema info added
    assert data["@context"] == "https://schema.org"
    # folder name normalisation
    assert recipe.folder_name == "a-b_test"


def test_parser_handles_cuisine_exception():
    mock_recipe = Mock()
    mock_recipe.title.return_value = "Name"
    mock_recipe.author.return_value = "Auth"
    mock_recipe.yields.return_value = 2
    mock_recipe.description.return_value = "Desc"
    mock_recipe.url = "http://example.com"
    mock_recipe.to_json.return_value = {"image": "img"}
    mock_recipe.schema.data = {"recipeInstructions": []}
    mock_recipe.category.return_value = "Cat"
    mock_recipe.keywords.return_value = []
    mock_recipe.dietary_restrictions.return_value = []
    mock_recipe.ingredients.return_value = []
    mock_recipe.nutrients.return_value = {}
    mock_recipe.cuisine.side_effect = Exception("boom")

    parser = DefaultRecipeParser(mock_recipe)
    result = parser.parse_recipe()
    # cuisine exception should simply be ignored
    assert result.keywords == []


def test_get_proper_parser_mapping():
    ah_parser = get_proper_parser("https://www.ah.nl/recipe")
    default_parser = get_proper_parser("https://example.com")
    assert ah_parser is AlbertHeijnRecipeParser
    assert issubclass(default_parser, DefaultRecipeParser)


def test_albertheijn_parser_special_fields():
    mock_recipe = Mock()
    mock_recipe.title.return_value = "Recipe"
    mock_recipe.author.return_value = "Chef"
    mock_recipe.yields.return_value = "4 porties"
    mock_recipe.description.return_value = ""
    mock_recipe.url = "https://www.ah.nl/r/test"
    mock_recipe.to_json.return_value = {"image": "img"}
    mock_recipe.schema.data = {"recipeInstructions": []}
    mock_recipe.category.return_value = ""
    mock_recipe.keywords.return_value = []
    mock_recipe.dietary_restrictions.return_value = []
    mock_recipe.ingredients.return_value = []
    mock_recipe.nutrients.return_value = {}
    mock_recipe.cuisine.side_effect = Exception("no cuisine")
    mock_recipe.soup.find_all.return_value = [SimpleNamespace(string="oven")]

    parser = AlbertHeijnRecipeParser(mock_recipe)
    result = parser.parse_recipe()
    assert result.tool == ["oven"]
    assert result.recipeYield == 4


def test_albertheijn_parser_handles_errors():
    mock_recipe = Mock()
    mock_recipe.title.return_value = "Recipe"
    mock_recipe.author.return_value = "Chef"
    mock_recipe.yields.side_effect = ["4 porties", Exception("yields")]
    mock_recipe.description.return_value = ""
    mock_recipe.url = "https://www.ah.nl/r/test"
    mock_recipe.to_json.return_value = {"image": "img"}
    mock_recipe.schema.data = {"recipeInstructions": []}
    mock_recipe.category.return_value = ""
    mock_recipe.keywords.return_value = []
    mock_recipe.dietary_restrictions.return_value = []
    mock_recipe.ingredients.return_value = []
    mock_recipe.nutrients.return_value = {}
    mock_recipe.cuisine.side_effect = Exception("no cuisine")
    mock_recipe.soup.find_all.side_effect = Exception("no tools")

    parser = AlbertHeijnRecipeParser(mock_recipe)
    result = parser.parse_recipe()
    assert result.tool == []
    assert result.recipeYield == "4 porties"


def test_abstract_parser_not_implemented():
    with pytest.raises(NotImplementedError):
        parsers.AbstractRecipeParser.parse_recipe(Mock())

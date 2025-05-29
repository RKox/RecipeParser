import unittest
from unittest.mock import Mock


from parsers import parse_ah_recipe


class TestParsing(unittest.TestCase):
    """
    Unit tests for the `parse_ah_recipe` function.

    This test suite verifies the behavior of the `parse_ah_recipe` function
    when provided with valid and missing recipe data.
    """

    def test_parses_valid_recipe_data(self):
        """
        Tests that a valid recipe scraper object is parsed correctly into a RecipeForCookBook object.

        The test ensures that all attributes of the parsed recipe match the expected values
        derived from the mock recipe scraper object.
        """
        mock_recipe = Mock()
        # mock_recipe.mock_add_spec(spec=AlbertHeijn, spec_set=True)
        mock_recipe.title.return_value = "Mock Recipe"
        mock_recipe.author.return_value = "Mock Author"
        mock_recipe.yields.return_value = "4 servings"
        mock_recipe.description.return_value = "Mock description"
        mock_recipe.schema.data = {
            "url": "http://example.com",
            "image": "http://example.com/image.jpg",
            "totalTime": "PT1H",
            "prepTime": "PT30M",
            "cookTime": "PT30M",
            "recipeInstructions": [{"step": "Mock step"}],
            "datePublished": "2023-01-01"
        }
        mock_recipe.category.return_value = "Mock Category"
        mock_recipe.keywords.return_value = ["keyword1", "keyword2"]
        mock_recipe.dietary_restrictions.return_value = ["restriction1"]
        mock_recipe.ingredients.return_value = ["ingredient1", "ingredient2"]
        mock_recipe.nutrients.return_value = {"calories": "200 kcal"}
        mock_recipe.cuisine.return_value = "Mock Cuisine"
        mock_recipe.soup.find_all.return_value = []
        mock_recipe.to_json.return_value = {"image": "http://example.com/image.jpg"}

        parsed_recipe = parse_ah_recipe(recipe=mock_recipe)

        self.assertEqual(parsed_recipe.name, "Mock Recipe")
        self.assertEqual(parsed_recipe.author, "Mock Author")
        self.assertEqual(parsed_recipe.recipeYield, 4)
        self.assertEqual(parsed_recipe.description, "Mock description")
        self.assertEqual(parsed_recipe.url, "http://example.com")
        self.assertEqual(parsed_recipe.image, "http://example.com/image.jpg")
        self.assertEqual(parsed_recipe.totalTime, "PT1H")
        self.assertEqual(parsed_recipe.prepTime, "PT30M")
        self.assertEqual(parsed_recipe.cookTime, "PT30M")
        self.assertEqual(parsed_recipe.recipeCategory, "Mock Category")
        self.assertEqual(parsed_recipe.keywords, ["keyword1", "keyword2", "restriction1", "Mock Cuisine"])
        # self.assertEqual(parsed_recipe.tool, ["Tool1", "Tool2"])
        self.assertEqual(parsed_recipe.recipeIngredient, ["ingredient1", "ingredient2"])
        self.assertEqual(parsed_recipe.recipeInstructions, [{"step": "Mock step"}])
        self.assertEqual(parsed_recipe.nutrition, {"calories": "200 kcal"})
        self.assertEqual(parsed_recipe.datePublished, "2023-01-01")

    def test_handles_missing_recipe_data(self):
        """
        Tests that missing recipe data is handled gracefully and defaults are applied.

        The test ensures that when the recipe scraper object has missing or empty attributes,
        the parsed recipe object uses default values for those attributes.
        """
        mock_recipe = Mock()
        # mock_recipe.mock_add_spec(spec=AlbertHeijn, spec_set=True)
        mock_recipe.title.return_value = "Mock Recipe"
        mock_recipe.author.return_value = ""
        mock_recipe.yields.return_value = "0 servings"
        mock_recipe.description.return_value = ""
        mock_recipe.schema.data = {}
        mock_recipe.category.return_value = ""
        mock_recipe.keywords.return_value = []
        mock_recipe.dietary_restrictions.return_value = []
        mock_recipe.ingredients.return_value = []
        mock_recipe.nutrients.return_value = {}
        mock_recipe.cuisine.return_value = ""
        mock_recipe.soup.find_all.return_value = []
        mock_recipe.to_json.return_value = {}


        parsed_recipe = parse_ah_recipe(recipe=mock_recipe)

        self.assertEqual(parsed_recipe.name, "Mock Recipe")
        self.assertEqual(parsed_recipe.author, "")
        self.assertEqual(parsed_recipe.recipeYield, 0)
        self.assertEqual(parsed_recipe.description, "")
        self.assertEqual(parsed_recipe.url, "")
        self.assertEqual(parsed_recipe.image, "")
        self.assertEqual(parsed_recipe.totalTime, "")
        self.assertEqual(parsed_recipe.prepTime, "")
        self.assertEqual(parsed_recipe.cookTime, "")
        self.assertEqual(parsed_recipe.recipeCategory, "")
        self.assertEqual(parsed_recipe.keywords, [])
        self.assertEqual(parsed_recipe.tool, [])
        self.assertEqual(parsed_recipe.recipeIngredient, [])
        self.assertEqual(parsed_recipe.recipeInstructions, [])
        self.assertEqual(parsed_recipe.nutrition, {})
        self.assertEqual(parsed_recipe.datePublished, "")


if __name__ == '__main__':
    unittest.main()

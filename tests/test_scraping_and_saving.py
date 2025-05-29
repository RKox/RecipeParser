import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from web_to_cookbook import get_urls_from_file, get_raw_recipe, save_to_json, get_and_save_image, web_to_cookbook


class TestWebToCookbook(unittest.TestCase):
    """
    Unit tests for the `web_to_cookbook` module.

    This test suite verifies the functionality of various methods used for
    extracting URLs, fetching recipe data, saving recipes to JSON, downloading
    images, and processing recipe URLs.
    """

    def test_extracts_urls_from_valid_file(self):
        """
        Tests that URLs are correctly extracted from a valid file containing URLs.
        """
        mock_file = MagicMock()
        mock_file.open.return_value.__enter__.return_value.read.return_value = "http://example.com\nnot a web url\nhttp://test.com"
        with patch("web_to_cookbook.URLExtract.find_urls", return_value=["http://example.com", "http://test.com"]):
            urls = get_urls_from_file(mock_file)
            self.assertEqual(urls, ["http://example.com", "http://test.com"])

    def test_handles_empty_file_for_url_extraction(self):
        """
        Tests that an empty file results in an empty list of URLs.
        """
        mock_file = MagicMock()
        mock_file.open.return_value.__enter__.return_value.read.return_value = ""
        with patch("web_to_cookbook.URLExtract.find_urls", return_value=[]):
            urls = get_urls_from_file(mock_file)
            self.assertEqual(urls, [])

    def test_fetches_recipe_data_from_valid_url(self):
        """
        Tests that recipe data is fetched correctly from a valid URL.
        """
        mock_response = MagicMock()
        mock_response.content.decode.return_value = "<html></html>"
        with patch("web_to_cookbook.requests.get", return_value=mock_response), \
             patch("web_to_cookbook.scrape_html", return_value=MagicMock(title=lambda: "Recipe Title", author=lambda: "Author")):
            recipe = get_raw_recipe("http://example.com")
            self.assertEqual(recipe.title(), "Recipe Title")
            self.assertEqual(recipe.author(), "Author")

    def test_raises_error_for_invalid_url(self):
        """
        Tests that an exception is raised when an invalid URL is provided.
        """
        with patch("web_to_cookbook.requests.get", side_effect=Exception("Invalid URL")):
            with self.assertRaises(Exception):
                get_raw_recipe("http://invalid-url.com")

    def test_saves_recipe_to_json_file(self):
        """
        Tests that recipe data is saved correctly to a JSON file.
        """
        mock_recipe = MagicMock()
        mock_recipe.folder_name = Path("/mock_folder")
        mock_recipe.to_json.return_value = {"name": "Mock Recipe"}
        with patch("web_to_cookbook.Path.open", mock_open()):
            path = save_to_json(mock_recipe)
            self.assertEqual(path, Path("/mock_folder/recipe.json"))

    def test_downloads_and_saves_image(self):
        """
        Tests that the recipe image is downloaded and saved correctly.
        """
        mock_recipe = MagicMock()
        mock_recipe.folder_name = Path("/mock_folder")
        mock_recipe.image = "http://example.com/image.jpg"
        with patch("web_to_cookbook.requests.get", return_value=MagicMock(content=b"image_data")), \
             patch("web_to_cookbook.Path.open", mock_open()):
            path = get_and_save_image(mock_recipe)
            self.assertEqual(path, Path("/mock_folder/full.jpg"))

    def test_processes_valid_recipe_url(self):
        """
        Tests that a valid recipe URL is processed correctly, including saving
        the recipe data and image to the appropriate folder.
        """
        mock_recipe_raw = MagicMock()
        mock_recipe_processed = MagicMock(folder_name=Path("/mock_folder"))
        with patch("web_to_cookbook.get_raw_recipe", return_value=mock_recipe_raw), \
             patch("web_to_cookbook.parse_ah_recipe", return_value=mock_recipe_processed), \
             patch("web_to_cookbook.Path.mkdir"), \
             patch("web_to_cookbook.save_to_json"), \
             patch("web_to_cookbook.get_and_save_image"):
            web_to_cookbook("http://example.com")


if __name__ == '__main__':
    unittest.main()
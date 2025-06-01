import shutil
import unittest
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock, mock_open, Mock
from pathlib import Path

from urlextract import URLExtract

from web_to_cookbook import get_urls_from_file, URLToCookbook

MOCK_PARENT_FOLDER = Path("mock_parent_folder")


@contextmanager
def temporary_directory():
    """
    Context manager to create a temporary directory for testing.
    """
    MOCK_PARENT_FOLDER.mkdir(exist_ok=True)
    try:
        with TemporaryDirectory(dir=MOCK_PARENT_FOLDER) as temp_dir:
            yield Path(temp_dir)
    finally:
        shutil.rmtree(MOCK_PARENT_FOLDER, ignore_errors=True)


@contextmanager
def temporary_file(initial_contents: str = ""):
    """
    Context manager to create a temporary file for testing.
    """
    with temporary_directory() as temp_dir:
        temp_file = temp_dir / "temp_file.txt"
        if initial_contents:
            with temp_file.open("w", encoding="utf-8") as f:
                f.write(initial_contents)
        yield temp_file


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
        with temporary_directory() as tmp_path:
            rtc = URLToCookbook(url_list=["http://example.com"], target_folder=tmp_path)
            with patch("web_to_cookbook.requests.Session.get", return_value=mock_response), \
                    patch("web_to_cookbook.scrape_html",
                          return_value=MagicMock(title=lambda: "Recipe Title", author=lambda: "Author")):
                recipe = rtc._get_recipe_from_url("http://example.com")
                self.assertEqual(recipe.title(), "Recipe Title")
                self.assertEqual(recipe.author(), "Author")

    def test_raises_error_for_invalid_url(self):
        """
        Tests that an exception is raised when an invalid URL is provided.
        """
        with temporary_directory() as tmp_path:
            rtc = URLToCookbook(url_list=["http://invalid-url.com"], target_folder=tmp_path)
            with patch("web_to_cookbook.requests.Session.get", side_effect=Exception("Invalid URL")):
                with self.assertRaises(Exception):
                    rtc._get_recipe_from_url("http://invalid-url.com")

    def test_creates_folder_with_correct_name(self):
        """
        Verifies that the folder is created with the correct name based on the recipe's folder name.
        """
        with temporary_directory() as tmp_path:
            rtc = URLToCookbook(url_list=["http://example.com"], target_folder=tmp_path)

            mock_recipe = Mock()
            mock_recipe.folder_name = "new_folder"

            created_folder = rtc._create_target_folder(recipe_processed=mock_recipe)

            self.assertTrue(created_folder.exists())
            self.assertEqual(created_folder.name, "new_folder")

    def test_creates_unique_folder_when_folder_name_exists(self):
        """
        Ensures that a unique folder is created when a folder with the same name already exists.
        """
        with temporary_directory() as tmp_path:
            rtc = URLToCookbook(url_list=["http://example.com"], target_folder=tmp_path)
            mock_recipe = Mock()
            mock_recipe.folder_name = "existing_folder"
            existing_folder = tmp_path / mock_recipe.folder_name
            existing_folder.mkdir(exist_ok=True)
            new_folder = rtc._create_target_folder(recipe_processed=mock_recipe)

            self.assertTrue(new_folder.exists())
            self.assertEqual("existing_folder_2", new_folder.name)
            self.assertNotEqual(existing_folder, new_folder)

    def test_saves_recipe_to_json_file(self):
        """
        Tests that recipe data is saved correctly to a JSON file.
        """
        with temporary_directory() as tmp_path:
            mock_recipe = MagicMock()
            mock_recipe.folder_name = Path("mock_folder")
            mock_recipe.to_json.return_value = {"name": "Mock Recipe"}
            rtc = URLToCookbook(url_list=["dummy"], target_folder=tmp_path)
            with patch("web_to_cookbook.Path.open", mock_open()):
                path = rtc._save_to_json(recipe_container=mock_recipe, target_folder=tmp_path / mock_recipe.folder_name)
                self.assertEqual(path, tmp_path / "mock_folder/recipe.json")

    def test_downloads_and_saves_image(self):
        """
        Tests that the recipe image is downloaded and saved correctly.
        """
        with temporary_directory() as tmp_path:
            mock_recipe = MagicMock()
            mock_recipe.folder_name = Path("mock_folder")
            mock_recipe.image = "http://example.com/image.jpg"
            rtc = URLToCookbook(url_list=["dummy"], target_folder=tmp_path)
            with patch("web_to_cookbook.requests.Session.get", return_value=MagicMock(content=b"image_data")), \
                    patch("web_to_cookbook.Path.open", mock_open()):
                path = rtc._get_and_save_image(recipe_container=mock_recipe,
                                               target_folder=tmp_path / mock_recipe.folder_name)
                self.assertEqual(path, tmp_path / "mock_folder/full.jpg")

    def test_processes_valid_recipe_url(self):
        """
        Tests that a valid recipe URL is processed correctly, including saving
        the recipe data and image to the appropriate folder.
        """
        with temporary_directory() as tmp_path:
            mock_recipe_raw = MagicMock()
            mock_recipe_processed = MagicMock(folder_name=Path("/mock_folder"))
            rtc = URLToCookbook(url_list=["http://example.com"], target_folder=tmp_path)
            with patch.object(rtc, "_get_recipe_from_url", return_value=mock_recipe_raw), \
                    patch("web_to_cookbook.parse_recipe", return_value=mock_recipe_processed), \
                    patch("web_to_cookbook.Path.mkdir"), \
                    patch.object(rtc, "_save_to_json"), \
                    patch.object(rtc, "_get_and_save_image"):
                rtc.web_to_cookbook("http://example.com")

    def test_appends_failed_urls_to_existing_file(self):
        """
        Ensures that failed URLs are appended to an existing file without duplicates.
        """
        initial_contents = "http://example.com\nhttp://test.com\n"
        expected_contents = "http://example.com\nhttp://test.com\nhttp://newurl.com\n"
        with temporary_file(initial_contents=initial_contents) as tmp_file:
            with temporary_directory() as tmp_path:
                rtc = URLToCookbook(url_list=["http://example.com", "http://newurl.com"], target_folder=tmp_path)
                rtc.failed_urls = list(rtc.url_set)
                rtc._update_failed_urls_file(file_path=tmp_file)

                file_urls = URLExtract().find_urls(tmp_file.read_text())
                expected_urls = URLExtract().find_urls(expected_contents)
                assert len(file_urls) == len(expected_urls)
                assert set(file_urls) == set(expected_urls)

    def test_creates_new_file_with_failed_urls(self):
        """
        Ensures that a new file is created and failed URLs are written when the file does not exist.
        """
        failing_url = ["http://example.com", "http://newurl.com"]
        with temporary_file() as tmp_file:
            with temporary_directory() as tmp_path:
                rtc = URLToCookbook(url_list=failing_url, target_folder=tmp_path)
                rtc.failed_urls = failing_url
                rtc._update_failed_urls_file(file_path=tmp_file)

                file_contents = set(tmp_file.read_text().splitlines())
                assert file_contents == set(failing_url)

    def test_success_urls_in_file(self):
        initial_contents = "http://example.com\nhttp://test.com\nhttp://success.com\n"
        expected_contents = "http://example.com\nhttp://test.com\nhttp://newurl.com\n"
        failing_urls = ["http://example.com", "http://newurl.com"]
        success_urls = ["http://success.com"]
        with temporary_file(initial_contents=initial_contents) as tmp_file:
            with temporary_directory() as tmp_path:
                rtc = URLToCookbook(url_list=failing_urls + success_urls, target_folder=tmp_path)
                rtc.failed_urls = failing_urls
                rtc.success_urls = success_urls
                rtc._update_failed_urls_file(file_path=tmp_file)

                file_urls = URLExtract().find_urls(tmp_file.read_text())
                expected_urls = URLExtract().find_urls(expected_contents)
                assert len(file_urls) == len(expected_urls)
                assert set(file_urls) == set(expected_urls)


if __name__ == '__main__':
    unittest.main()

import argparse
import shutil
import time
import traceback

import requests
from recipe_scrapers import scrape_html, AbstractScraper
import json
from pathlib import Path

from parsers import parse_ah_recipe, RecipeForCookBook
from urlextract import URLExtract

# Constants for file paths and headers
RECIPES_FOLDER = Path("parsed_recipes")  # Folder where all recipes will be saved
IMAGE_FILENAME = Path("full.jpg")  # Default filename for recipe images
RECIPE_FILENAME = Path("recipe.json")  # Default filename for recipe JSON data
HEADERS = {"User-Agent": "Mozilla/5.0"}  # HTTP headers for web requests
FAILED_URLS_FILE = Path("failed_urls.txt")  # File to store failed URLs


class RecipeToCookbook:
    """
    Class to handle the conversion of web recipes to a cookbook format.
    This class provides methods to extract URLs from files, fetch and parse recipes,
    save recipe data and images, and manage the overall process of converting web recipes.
    """

    def __init__(self, url_list: list[str], target_folder: Path):
        """
        Initializes the RecipeToCookbook class with a list of URLs and a target folder.

        :param url_list: A list of recipe URLs to process.
        :param target_folder: The folder where all output recipes will be saved.
        """
        assert url_list, "URL list cannot be empty. Please provide at least one URL."
        self.url_list: list[str] = url_list
        self.target_folder: Path = target_folder
        self.recipes: list[RecipeForCookBook] = []
        self.failed_urls = []
        self.success_urls = []
        self.urls_and_paths: dict[str, Path] = {}

        if not self.target_folder.exists():
            self.target_folder.mkdir(parents=False, exist_ok=False)
            print(f"Created target folder: {self.target_folder}")

    def _get_raw_recipe(self, url: str) -> AbstractScraper:
        """
        Fetches and parses raw recipe data from a given URL.

        :param url: The URL of the recipe to scrape.
        :return: An AbstractScraper object containing the raw recipe data.
        """
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        html = res.content.decode("utf-8")
        recipe = scrape_html(html=html, org_url=url, online=True, supported_only=True)
        print(f"Received recipe for '{recipe.title()}' by '{recipe.author()}'")
        return recipe

    def _get_and_save_image(self, recipe: RecipeForCookBook, target_folder: Path) -> Path:
        """
        Downloads and saves the recipe image to a file.

        :param recipe: A RecipeForCookBook object containing recipe details.
        :param target_folder: The parent folder under which the image will be saved.
        :return: Path to the saved image file.
        """
        image_data: bytes = requests.get(recipe.image).content
        file_path = target_folder / IMAGE_FILENAME
        with file_path.open(mode='wb') as f:
            f.write(image_data)

        print(f"Saved image as {file_path}")
        return file_path

    def _save_to_json(self, recipe: RecipeForCookBook, target_folder: Path) -> Path:
        """
        Saves the recipe data to a JSON file.

        :param recipe: A RecipeForCookBook object containing recipe details.
        :param target_folder: The parent folder under which the JSON file will be saved.
        :return: Path to the saved JSON file.
        """
        filename = target_folder / RECIPE_FILENAME
        with filename.open("w", encoding="utf-8") as f:
            json.dump(recipe.to_json(), f, indent=2, ensure_ascii=False)
        print(f"Saved recipe as {filename}")
        return filename

    def web_to_cookbook(self, url: str):
        """
        Processes a recipe URL and saves its data and image to files.

        :param url: The URL of the recipe to process.
        """
        print(f"Processing recipe from URL: {url}")
        try:
            recipe_raw = self._get_raw_recipe(url=url)
            recipe_processed = parse_ah_recipe(recipe=recipe_raw)
            target_folder = self._create_target_folder(recipe_processed)
            self.urls_and_paths[url] = target_folder
            self._save_to_json(recipe=recipe_processed, target_folder=target_folder)
            self._get_and_save_image(recipe=recipe_processed, target_folder=target_folder)
        except Exception as e:
            self.failed_urls.append(url)
            if url in self.urls_and_paths:
                print(f"Failed to process {url}, removing from URLs and paths list.")
                path = self.urls_and_paths.pop(url)
                if path.exists():
                    print(f"Removing folder {path} due to failure.")
                    shutil.rmtree(path)

            raise e
        else:
            if url in self.failed_urls:
                print(f"Successfully processed {url}, removing from failed URLs list.")
                self.failed_urls.remove(url)  # Remove URL from failed list if successful

    def _create_target_folder(self, recipe_processed: RecipeForCookBook) -> Path:
        """Creates a target folder for the recipe based on its folder name."""
        i = 1
        target_folder = self.target_folder / recipe_processed.folder_name
        while target_folder.exists():
            i += 1
            new_name = f"{recipe_processed.folder_name}_{i}"
            print(f"Folder {target_folder} already exists, trying '{new_name}'")
            target_folder = (target_folder.with_name(new_name))
        Path(target_folder).mkdir(exist_ok=False)
        return target_folder

    def run_through_urls(self) -> None:
        """
        Main function to process a list of recipe URLs.

        :raises ExceptionGroup: If any exceptions occur during processing.
        """
        exceptions: list[Exception] = []
        for url in self.url_list:
            try:
                self.web_to_cookbook(url)
            except Exception as e:
                exceptions.append(e)
                print(f"Error processing {url}:\n{traceback.format_exc()}")
                continue

        if self.failed_urls:
            self._update_failed_urls_file(file_path=self.target_folder / FAILED_URLS_FILE)

        if exceptions:
            raise ExceptionGroup(f"{len(exceptions)} exceptions raised during scraping!", exceptions)

    def run_with_retry(self, retries: int = 3) -> None:
        """
        Runs the recipe processing with a specified number of retries for failed URLs.

        :param retries: Number of times to retry processing failed URLs.
        """
        for attempt in range(retries):
            print(f"Attempt {attempt + 1} of {retries}")
            try:
                self.run_through_urls()
            except ExceptionGroup as e:
                print(f"Encountered {len(e.exceptions)} errors during processing:\n{traceback.format_exc()}")

            if not self.failed_urls:
                print("All URLs processed successfully.")
                break
            else:
                print(f"Retrying {len(self.failed_urls)} failed URLs...")
                self.url_list = self.failed_urls
                self.failed_urls = []
                time.sleep(2)  # allow for a brief pause before retrying

        if self.failed_urls:
            print(f"Failed to process {len(self.failed_urls)} URLs after {retries} attempts.")

    def _update_failed_urls_file(self, file_path: Path) -> None:
        """
        Updates a file with the failed URLs from this session, ensuring no duplicates.

        :param file_path: Path to the file where failed URLs are stored.
        """
        print(f"Updating failed URLs file: {file_path}")
        failed_urls = set()
        if file_path.exists():
            with file_path.open("r", encoding="utf-8") as f:
                failed_urls.update(URLExtract().find_urls(f.read()))

        # remove any URLs that were successfully processed in this run
        failed_urls.difference_update(set(self.success_urls))

        failed_urls.update(self.failed_urls)
        with file_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(failed_urls))


def get_urls_from_file(url_file: Path) -> list[str]:
    """
    Extracts URLs from a given file.

    :param url_file: Path to the file containing URLs.
    :return: A list of URLs extracted from the file.
    """
    extractor = URLExtract()
    with url_file.open("r", encoding="utf-8") as f:
        contents = f.read()

    print(f"Extracting URLs from {url_file}")
    urls = extractor.find_urls(contents)
    print(f"Found {len(urls)} URLs in {url_file}")
    return urls


if __name__ == "__main__":
    # Command-line argument parser for recipe URLs and files containing URLs
    parser = argparse.ArgumentParser(description="Scrape recipes from URLs or files containing URLs.")
    parser.add_argument("-u", "--url", action="append", help="Recipe URLs to scrape", default=[])
    parser.add_argument("-f", "--file", action="append", help="Files containing recipe URLs", default=[])
    parser.add_argument(
        "-t", "--target", help="Target folder which will hold all output recipes", default=RECIPES_FOLDER
    )
    args: argparse.Namespace = parser.parse_args()

    # Combine URLs from command-line arguments and files
    urls: list[str] = args.url
    for file in args.file:
        urls.extend(get_urls_from_file(url_file=Path(file)))

    # Process the URLs
    recipe_to_cookbook = RecipeToCookbook(url_list=urls, target_folder=Path(args.target))
    recipe_to_cookbook.run_with_retry(retries=3)

    for file in args.file:
        print(f"Removing file {file} after processing.")
        Path(file).unlink(missing_ok=True)

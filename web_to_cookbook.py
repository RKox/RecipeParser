import argparse

import requests
from recipe_scrapers import scrape_html, AbstractScraper
import json
from pathlib import Path

from parsers import parse_ah_recipe, RecipeForCookBook
from urlextract import URLExtract

# Constants for file paths and headers
RECIPE_FOLDER = "/Recipes"  # Folder where recipes will be saved (TODO: make configurable)
IMAGE_FILENAME = Path("full.jpg")  # Default filename for recipe images
RECIPE_FILENAME = Path("recipe.json")  # Default filename for recipe JSON data
HEADERS = {"User-Agent": "Mozilla/5.0"}  # HTTP headers for web requests


def get_urls_from_file(url_file: Path) -> list[str]:
    """
    Extracts URLs from a given file.

    :param url_file: Path to the file containing URLs.
    :return: A list of URLs extracted from the file.
    """
    extractor = URLExtract()
    with url_file.open("r") as f:
        contents = f.read()

    return extractor.find_urls(contents)


def get_raw_recipe(url: str) -> AbstractScraper:
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


def get_and_save_image(recipe: RecipeForCookBook) -> Path:
    """
    Downloads and saves the recipe image to a file.

    :param recipe: A RecipeForCookBook object containing recipe details.
    :return: Path to the saved image file.
    """
    image_data: bytes = requests.get(recipe.image).content
    file_path = (recipe.folder_name / IMAGE_FILENAME)
    with file_path.open(mode='wb') as f:
        f.write(image_data)

    print(f"Saved image as {file_path}")
    return file_path


def save_to_json(recipe: RecipeForCookBook) -> Path:
    """
    Saves the recipe data to a JSON file.

    :param recipe: A RecipeForCookBook object containing recipe details.
    :return: Path to the saved JSON file.
    """
    filename = Path(recipe.folder_name) / RECIPE_FILENAME
    with filename.open("w", encoding="utf-8") as f:
        json.dump(recipe.to_json(), f, indent=2, ensure_ascii=False)
    print(f"Saved recipe as {filename}")
    return filename


def web_to_cookbook(url: str):
    """
    Processes a recipe URL and saves its data and image to files.

    :param url: The URL of the recipe to process.
    """
    recipe_raw = get_raw_recipe(url=url)
    recipe_processed = parse_ah_recipe(recipe=recipe_raw)
    # Save files to subfolder
    Path(recipe_processed.folder_name).mkdir(exist_ok=False)
    save_to_json(recipe=recipe_processed)
    get_and_save_image(recipe=recipe_processed)


def main(url_list: [str]) -> None:
    """
    Main function to process a list of recipe URLs.

    :param url_list: A list of recipe URLs to process.
    :raises ExceptionGroup: If any exceptions occur during processing.
    """
    exceptions: list[Exception] = []
    for url in url_list:
        try:
            web_to_cookbook(url)
        except Exception as e:
            exceptions.append(e)
            continue

    if exceptions:
        raise ExceptionGroup(f"{len(exceptions)} exceptions raised during scraping!", exceptions)


if __name__ == "__main__":
    # Command-line argument parser for recipe URLs and files containing URLs
    parser = argparse.ArgumentParser(description="Scrape recipes from URLs or files containing URLs.")
    parser.add_argument("-u", "--url", action="append", help="Recipe URLs to scrape", default=[])
    parser.add_argument("-f", "--file", action="append", help="Files containing recipe URLs", default=[])
    args: argparse.Namespace = parser.parse_args()

    # Combine URLs from command-line arguments and files
    urls: [str] = args.url
    for file in args.file:
        urls.extend(get_urls_from_file(url_file=Path(file)))

    # Process the URLs
    main(url_list=urls)

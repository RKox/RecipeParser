import argparse

import requests
from recipe_scrapers import scrape_html, AbstractScraper
import json
from pathlib import Path

from parsers import parse_ah_recipe, RecipeForCookBook
from urlextract import URLExtract

# Constants for file paths and headers
RECIPES_FOLDER = Path("parsed_recipes")  # Folder where all recipes will be saved (TODO: make configurable)
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
    with url_file.open("r", encoding="utf-8") as f:
        contents = f.read()

    print(f"Extracting URLs from {url_file}")
    urls = extractor.find_urls(contents)
    print(f"Found {len(urls)} URLs in {url_file}")
    return urls


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


def get_and_save_image(recipe: RecipeForCookBook, target_folder: Path) -> Path:
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


def save_to_json(recipe: RecipeForCookBook, target_folder: Path) -> Path:
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


def web_to_cookbook(url: str):
    """
    Processes a recipe URL and saves its data and image to files.

    :param url: The URL of the recipe to process.
    """
    recipe_raw = get_raw_recipe(url=url)
    recipe_processed = parse_ah_recipe(recipe=recipe_raw)

    # Save files to subfolder
    i=1
    target_folder = RECIPES_FOLDER / recipe_processed.folder_name
    while target_folder.exists():
        i += 1
        new_name = f"{recipe_processed.folder_name}_{i}"
        print(f"Folder {target_folder} already exists, trying '{new_name}'")
        target_folder = (target_folder.with_name(new_name))

    Path(target_folder).mkdir(exist_ok=False)
    save_to_json(recipe=recipe_processed, target_folder=target_folder)
    get_and_save_image(recipe=recipe_processed, target_folder=target_folder)


def main(url_list: [str], target_folder: Path) -> None:
    """
    Main function to process a list of recipe URLs.

    :param url_list: A list of recipe URLs to process.
    :param target_folder: The folder where all output recipes will be saved.
    :raises ExceptionGroup: If any exceptions occur during processing.
    """
    exceptions: list[Exception] = []
    if not target_folder.exists():
        target_folder.mkdir(parents=False, exist_ok=False)

    for url in url_list:
        try:
            web_to_cookbook(url)
        except Exception as e:
            exceptions.append(e)
            print(f"Error processing {url}:\n{e}")
            continue

    if exceptions:
        raise ExceptionGroup(f"{len(exceptions)} exceptions raised during scraping!", exceptions)


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
    urls: [str] = args.url
    for file in args.file:
        urls.extend(get_urls_from_file(url_file=Path(file)))

    # Process the URLs
    main(url_list=urls, target_folder=Path(args.target))

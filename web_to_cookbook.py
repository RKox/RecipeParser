import argparse
import os
import shutil
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, auto
from typing import Generator, Any
from requests_html import HTMLSession, HTML
import pickle

import netifaces
from bs4 import BeautifulSoup
from requests import Session
from requests.adapters import HTTPAdapter
from recipe_scrapers import scrape_html, AbstractScraper
import json
from pathlib import Path

from parsers import parse_recipe, RecipeForCookBook, get_proper_parser
from urlextract import URLExtract

# Constants for file paths and headers
RECIPES_FOLDER = Path("parsed_recipes")  # Folder where all recipes will be saved
IMAGE_FILENAME = Path("full.jpg")  # Default filename for recipe images
RECIPE_FILENAME = Path("recipe.json")  # Default filename for recipe JSON data
FAILED_URLS_FILE = Path("failed_urls.txt")  # File to store failed URLs
COOKIEJAR = Path("cookies.pkl")  # File to store cookies for requests

PYPPETEER_CHROMIUM_REVISION = '1181205'
os.environ['PYPPETEER_CHROMIUM_REVISION'] = PYPPETEER_CHROMIUM_REVISION


def get_source_ip(interface: str = "") -> str:
    """
    Retrieves the source IP address for a given network interface.
    If no interface is specified, it defaults to '127.0.0.1'.
    If the specified interface is not found, it raises a ValueError.
    If the interface does not have an IPv4 address, it raises a ValueError.

    :param interface: The name of the network interface (e.g., 'eth0', 'wlan0').
    :return: The IP address as a string.
    """
    if not interface:
        return "127.0.0.1"
    if interface not in (ifs := netifaces.interfaces()):
        raise ValueError(f"Interface '{interface}' not found. Choose from: {ifs}")
    addresses = netifaces.ifaddresses(interface)
    if netifaces.AF_INET not in addresses:
        raise ValueError(f"No IPv4 address found for interface '{interface}'. \nAvailable interfaces: {ifs}")

    return addresses[netifaces.AF_INET][0]['addr']


class SourceIPAdapter(HTTPAdapter):
    """
    Custom HTTPAdapter that allows setting a specific source IP address for requests.
    This is useful for scenarios where requests need to originate from a specific IP,
    such as when using a multi-homed server or specific network interface.

    :param source_ip: The source IP address to use for requests.
    """

    def __init__(self, source_ip, **kwargs):
        self.source_ip = source_ip
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['source_address'] = (self.source_ip, 0)
        return super().init_poolmanager(*args, **kwargs)


class Source(Enum):
    html = auto()
    url = auto()


@dataclass
class RecipeContainer:
    source: Source
    source_content: str
    success: bool = False
    raw_recipe: AbstractScraper | None = None
    parsed_recipe: RecipeForCookBook | None = None
    target_folder: Path | None = None

    def __hash__(self) -> int:
        return hash(self.source_content)


class HTMLToCookbook:

    def __init__(self, target_folder: Path, html_list: list[str] | None = None, interface: str = ""):
        if not html_list:
            assert type(self) is not HTMLToCookbook, "No HTMLs provided for processing."
            html_list = []

        self.target_folder: Path = target_folder
        self._interface: str = interface
        self._source_recipes: set[RecipeContainer] = {
            RecipeContainer(source=Source.html, source_content=html) for html in html_list
        }

        if not self.target_folder.exists():
            self.target_folder.mkdir(parents=False, exist_ok=False)
            print(f"Created target folder: {self.target_folder}")

    @property
    def success_recipes(self) -> list[RecipeContainer]:
        return [r for r in self._source_recipes if r.success]

    @property
    def not_success_recipes(self) -> list[RecipeContainer]:
        return [r for r in self._source_recipes if not r.success]

    @contextmanager
    def _get_new_session(self) -> Generator[Session, Any, None]:
        """
        Creates a new requests session with a custom source IP address based on the specified network interface.
        :return: A requests Session object with the source IP set.
        """
        with HTMLSession() as session:
            source_ip = get_source_ip(interface=self._interface)
            session.mount('http://', SourceIPAdapter(source_ip))
            session.mount('https://', SourceIPAdapter(source_ip))
            if not COOKIEJAR.exists():
                COOKIEJAR.touch()
            else:
                with COOKIEJAR.open('rb') as f:
                    session.cookies.update(pickle.load(f))
            try:
                yield session
            finally:
                with COOKIEJAR.open('wb') as f:
                    pickle.dump(session.cookies, f)

    @staticmethod
    def _html_to_recipe(html: str = "", url: str = "", supported_only: bool = True) -> AbstractScraper:
        """
        Parses raw HTML content to extract recipe data.
        If no URL is provided, it attempts to extract the first valid URL from the HTML content.
        If the HTML does not contain a valid URL, it raises an error.
        If the URL is provided, it uses that as the source URL for the recipe.
        If `supported_only` is True, it only processes recipes from supported sites.
        If `supported_only` is False, it processes all recipes regardless of support.
        This method uses the `scrape_html` function to parse the HTML and return a recipe object.

        :param html: The raw HTML content of the recipe to parse.
        :param url: The URL of the recipe. If not provided, it will be extracted from the HTML.
        :param supported_only: If True, only processes recipes from supported sites.
        :return: An AbstractScraper object containing the parsed recipe data.
        """
        if not url:
            html_obj = HTML(html=html)
            url = html_obj.links[0]  # Use the first URL found in the HTML as the source URL
            # soup = BeautifulSoup(html, "html.parser")
            # links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].startswith(('http://', 'https://'))]
            # srcs = [tag['src'] for tag in soup.find_all(src=True)]
            # urls = links + srcs
            # url = urls[0]  # Use the first URL found in the HTML as the source URL

        recipe = scrape_html(html=html, org_url=url, supported_only=supported_only)
        print(f"Parsed recipe for '{recipe.title()}' by '{recipe.author()}'")
        return recipe

    def _get_and_save_image(self, recipe_container: RecipeContainer) -> Path:
        with self._get_new_session() as session:
            image_data: bytes = session.get(recipe_container.parsed_recipe.image).content

        file_path = recipe_container.target_folder / IMAGE_FILENAME
        with file_path.open(mode='wb') as f:
            f.write(image_data)

        print(f"Saved image as {file_path}")
        return file_path

    @staticmethod
    def _save_to_json(recipe_container: RecipeContainer) -> Path:
        filename = recipe_container.target_folder / RECIPE_FILENAME
        with filename.open("w", encoding="utf-8") as f:
            json.dump(recipe_container.parsed_recipe.to_json(), f, indent=2, ensure_ascii=False)
        print(f"Saved recipe as {filename}")
        return filename

    def html_to_cookbook(self, recipe_container: RecipeContainer):
        print(f"Processing recipe from html content.")
        assert recipe_container.source is Source.html, "RecipeContainer must have source set to 'html'."
        recipe_container.raw_recipe = self._html_to_recipe(html=recipe_container.source_content, supported_only=False)
        self._save_scraped_recipe(recipe_container=recipe_container)

    def _save_scraped_recipe(self, recipe_container: RecipeContainer) -> None:
        recipe_container.parsed_recipe = parse_recipe(recipe=recipe_container.raw_recipe)
        recipe_container.target_folder = self._create_target_folder(recipe_container=recipe_container)
        self._save_to_json(recipe_container=recipe_container)
        self._get_and_save_image(recipe_container=recipe_container)

    def run_through_htmls(self) -> None:
        """
        Main function to process a list of HTML content.
        """
        exceptions: list[Exception] = []
        for container in self.not_success_recipes:
            if container.source is not Source.html:
                continue

            try:
                self.html_to_cookbook(recipe_container=container)
                container.success = True
            except Exception as e:
                exceptions.append(e)
                print(f"Error processing HTML content:\n{traceback.format_exc()}")

        if exceptions:
            raise ExceptionGroup(f"{len(exceptions)} exceptions raised during HTML processing!", exceptions)

    def _create_target_folder(self, recipe_container: RecipeContainer) -> Path:
        """Creates a target folder for the recipe based on its folder name."""
        assert recipe_container.parsed_recipe, "RecipeContainer must have parsed_recipe set before creating target folder."
        i = 1
        recipe_container.target_folder = self.target_folder / recipe_container.parsed_recipe.folder_name
        while recipe_container.target_folder.exists():
            i += 1
            new_name = f"{recipe_container.parsed_recipe.folder_name}_{i}"
            print(f"Folder {recipe_container.target_folder} already exists, trying '{new_name}'")
            recipe_container.target_folder = (recipe_container.target_folder.with_name(new_name))
        recipe_container.target_folder.mkdir(exist_ok=False)
        return recipe_container.target_folder


class URLToCookbook(HTMLToCookbook):

    def __init__(self, url_list: list | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert url_list, "No URLs provided for processing."
        if url_list is None:
            url_list = []

        self._source_recipes.update({RecipeContainer(source=Source.url, source_content=url) for url in url_list})

    def _get_recipe_from_url(self, recipe_container: RecipeContainer) -> AbstractScraper:
        assert recipe_container.source is Source.url, "RecipeContainer must have source set to 'url'."
        html = self._get_html_from_url(url=recipe_container.source_content)
        recipe_container.raw_recipe = self._html_to_recipe(html=html, url=recipe_container.source_content)
        return recipe_container.raw_recipe

    def _get_html_from_url(self, url: str) -> str:
        """
        Fetches the HTML content from a given URL.
        Uses the appropriate headers based on the parser for the URL.

        :param url: The URL to fetch the HTML content from.
        :return:  The HTML content as a string.
        """
        headers = get_proper_parser(url=url).HEADERS
        with self._get_new_session() as session:
            res = session.get(url, headers=headers, allow_redirects=False)

        res.raise_for_status()
        return res.content.decode("utf-8")

    def web_to_cookbook(self, recipe_container: RecipeContainer):
        assert recipe_container.source is Source.url, "RecipeContainer must have source set to 'url'."
        print(f"Processing recipe from URL: {recipe_container.source_content}")
        try:
            self._get_recipe_from_url(recipe_container=recipe_container)
            self._save_scraped_recipe(recipe_container=recipe_container)
            recipe_container.success = True
        except Exception as e:
            if recipe_container.target_folder is not None and recipe_container.target_folder.exists():
                shutil.rmtree(recipe_container.target_folder)
                print(f"Removed folder {recipe_container.target_folder} due to failure in"
                      f" processing {recipe_container.source_content}")

            raise e

    def run_through_urls(self) -> None:
        """
        Main function to process a list of recipe URLs.

        :raises ExceptionGroup: If any exceptions occur during processing.
        """
        exceptions: list[Exception] = []
        for container in self.not_success_recipes:
            if container.source is not Source.url:
                continue

            try:
                self.web_to_cookbook(recipe_container=container)
            except Exception as e:
                exceptions.append(e)
                print(f"Error processing {container.source_content}:\n{traceback.format_exc()}")
                continue

        self._update_failed_urls_file(file_path=self.target_folder / FAILED_URLS_FILE)

        if exceptions:
            raise ExceptionGroup(f"{len(exceptions)} exceptions raised during scraping!", exceptions)

    def run_through_urls_with_retry(self, retries: int = 3) -> None:
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

            if not (failed_urls := [f for f in self.not_success_recipes if f.source is Source.url]):
                print("All URLs processed successfully.")
                break
            else:
                print(f"Retrying {len(failed_urls)} failed URLs...")
                time.sleep(2)  # allow for a brief pause before retrying

        if failed_urls := [f for f in self.not_success_recipes if f.source is Source.url]:
            print(f"Failed to process {len(failed_urls)} URLs after {retries} attempts.")

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
        failed_urls.difference_update(set((r.source_content for r in self.success_recipes if r.source is Source.url)))

        failed_urls.update(r.source_content for r in self.not_success_recipes if r.source is Source.url)
        with file_path.open("w", encoding="utf-8") as f:
            f.truncate(0)  # Clear the file before writing
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
    parser.add_argument("-i", "--interface", type=str,
                        help="Which network interace to use (e.g. end0). "
                             "If no interface is specified, it defaults to '127.0.0.1'",
                        default="")
    parser.add_argument("-u", "--url", action="append", help="Recipe URLs to scrape", default=[])
    parser.add_argument("-f", "--file", action="append", help="Files containing recipe URLs, or HTML for parsing",
                        default=[])
    parser.add_argument(
        "-t", "--target", help="Target folder which will hold all output recipes", default=RECIPES_FOLDER
    )
    args: argparse.Namespace = parser.parse_args()

    # Combine URLs from command-line arguments and files
    # A file can also be a local HTML file, in which case we will parse that file directly
    urls: list[str] = args.url
    htmls: list[str] = []
    for file in args.file:
        filepath = Path(file)
        contents = filepath.read_text(encoding="utf-8").strip()
        if contents.startswith("<!DOCTYPE html>"):
            htmls.append(contents)
        else:
            urls.extend(get_urls_from_file(url_file=filepath))

    urls = [url.strip() for url in urls if url.strip()]  # Remove any empty URLs, and remove any whitespace

    # Process the recipes
    recipe_to_cookbook = URLToCookbook(url_list=urls, html_list=htmls, target_folder=Path(args.target),
                                       interface=args.interface)
    if urls:
        recipe_to_cookbook.run_through_urls_with_retry(retries=3)
    if htmls:
        recipe_to_cookbook.run_through_htmls()

    for file in args.file:
        print(f"Removing file {file} after processing.")
        Path(file).unlink(missing_ok=True)

from dataclasses import dataclass, field, asdict
from functools import cached_property

import requests
from recipe_scrapers import scrape_html
import json
import sys
from pathlib import Path
import logging
# from systemd.journal import JournalHandler

RECIPE_FOLDER = "/Recipes"
IMAGE_FILENAME = Path("full.jpg")
RECIPE_FILENAME = Path("recipe.json")
HEADERS = {"User-Agent": "Mozilla/5.0"}
SCHEMA = {"@context": "https://schema.org", "@type": "Recipe"}


@dataclass
class RecipeForCookBook:
    """
    TODO
    """

    name: str
    recipeYield: int
    author: str = ""
    description: str = ""
    url: str = ""
    image: str = ""  # URL
    prepTime: str = ""
    cookTime: str = ""
    totalTime: str = ""
    recipeCategory: str = ""
    keywords: list[str] = field(default_factory=list)
    tool: list[str] = field(default_factory=list)
    recipeIngredient: list[str] = field(default_factory=list)
    recipeInstructions: list[dict] = field(default_factory=list)
    nutrition: dict[str] = field(default_factory=dict)
    datePublished: str = ""

    def to_json(self):
        as_dict = asdict(self)
        empty_elements = [k for k, v in as_dict.items() if not v]
        for k in empty_elements:
            as_dict.pop(k)

        as_dict.update(SCHEMA)
        return as_dict

    @cached_property
    def folder_name(self) -> str:
        return self.name.lower().replace(" ", "_").replace("/", "-")


def fetch_ah_recipe(url):
    """
    TODO

    :param url:
    :return:
    """
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    html = res.content.decode("utf-8")
    recipe = scrape_html(html=html, org_url=url, online=True, supported_only=True)
    apps = recipe.soup.find_all("ul", {"data-testhook": "appliances"})

    cookbook_recipe = RecipeForCookBook(
        name=recipe.title(),
        author=recipe.author(),
        recipeYield=int(recipe.yields().strip(" servings")),
        description=recipe.description(),
        url=recipe.schema.data.get("url", ""),
        image=recipe.to_json()["image"],
        totalTime=recipe.schema.data.get("totalTime", ""),
        prepTime=recipe.schema.data.get("prepTime", ""),
        cookTime=recipe.schema.data.get("cookTime", ""),
        recipeCategory=recipe.category(),
        keywords=recipe.keywords() + recipe.dietary_restrictions(),
        tool=[a.string for a in apps],
        recipeIngredient=recipe.ingredients(),
        recipeInstructions=recipe.schema.data['recipeInstructions'],
        nutrition=recipe.nutrients(),
        datePublished=recipe.schema.data.get("datePublished", "")
    )
    if recipe.cuisine():
        cookbook_recipe.keywords.append(recipe.cuisine())

    print(f"Received recipe for '{cookbook_recipe.name}' by '{cookbook_recipe.author}'")

    return cookbook_recipe


def get_image(recipe: RecipeForCookBook) -> Path:
    """

    :param recipe:
    :return:
    """
    image_data: bytes = requests.get(recipe.image).content
    file_path = (recipe.folder_name / IMAGE_FILENAME)
    with file_path.open(mode='wb') as f:
        f.write(image_data)

    print(f"Saved image as {file_path}")
    return file_path


def main():
    if len(sys.argv) < 2:
        print("Use: python ah2cookbook.py <recept-url>")
        return

    url = sys.argv[1]
    recipe = fetch_ah_recipe(url=url)

    # Save files
    Path(recipe.folder_name).mkdir(exist_ok=True)
    get_image(recipe=recipe)
    save_to_json(recipe=recipe)


def save_to_json(recipe: RecipeForCookBook) -> Path:
    filename = Path(recipe.folder_name) / RECIPE_FILENAME
    with filename.open("w", encoding="utf-8") as f:
        json.dump(recipe.to_json(), f, indent=2, ensure_ascii=False)
    print(f"Saved recipe as {filename}")
    return filename


if __name__ == "__main__":
    main()

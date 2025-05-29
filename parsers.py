from dataclasses import dataclass, field, asdict
from functools import cached_property

from recipe_scrapers import AbstractScraper

# Schema for the recipe JSON structure
SCHEMA = {"@context": "https://schema.org", "@type": "Recipe"}

@dataclass
class RecipeForCookBook:
    """
    Represents a recipe formatted for a cookbook.

    Attributes:
        name (str): The name of the recipe.
        recipeYield (int): The number of servings the recipe yields.
        author (str): The author of the recipe. Defaults to an empty string.
        description (str): A brief description of the recipe. Defaults to an empty string.
        url (str): The URL of the recipe. Defaults to an empty string.
        image (str): The URL of the recipe image. Defaults to an empty string.
        prepTime (str): The preparation time for the recipe. Defaults to an empty string.
        cookTime (str): The cooking time for the recipe. Defaults to an empty string.
        totalTime (str): The total time required for the recipe. Defaults to an empty string.
        recipeCategory (str): The category of the recipe. Defaults to an empty string.
        keywords (list[str]): A list of keywords associated with the recipe. Defaults to an empty list.
        tool (list[str]): A list of tools required for the recipe. Defaults to an empty list.
        recipeIngredient (list[str]): A list of ingredients for the recipe. Defaults to an empty list.
        recipeInstructions (list[dict]): A list of instructions for the recipe. Defaults to an empty list.
        nutrition (dict[str]): Nutritional information for the recipe. Defaults to an empty dictionary.
        datePublished (str): The date the recipe was published. Defaults to an empty string.
    """

    name: str
    recipeYield: int
    author: str = ""
    description: str = ""
    url: str = ""
    image: str = ""  # URL to image
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
        """
        Converts the recipe object to a JSON-compatible dictionary.

        Removes any attributes with empty values and adds the schema information.

        Returns:
            dict: A dictionary representation of the recipe object.
        """
        as_dict = asdict(self)
        empty_elements = [k for k, v in as_dict.items() if not v]
        for k in empty_elements:
            as_dict.pop(k)

        as_dict.update(SCHEMA)
        return as_dict

    @cached_property
    def folder_name(self) -> str:
        """
        Generates a folder name for the recipe based on its name.

        Replaces spaces with underscores and removes invalid characters.

        Returns:
            str: The folder name for the recipe.
        """
        return self.name.lower().replace(" ", "_").replace("/", "-")


def parse_ah_recipe(recipe: AbstractScraper):
    """
    Parses a recipe from an Albert Heijn recipe scraper object.

    Extracts relevant data and formats it into a `RecipeForCookBook` object.

    Args:
        recipe (AbstractScraper): The recipe scraper object containing raw recipe data.

    Returns:
        RecipeForCookBook: A formatted recipe object ready for saving.
    """
    apps = recipe.soup.find_all("ul", {"data-testhook": "appliances"})  # Find all tools needed for recipe
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

    return cookbook_recipe

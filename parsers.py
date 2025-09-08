from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from functools import cached_property
from urllib.parse import urlparse
from typing import Dict, List, Optional

from recipe_scrapers import AbstractScraper

# Schema for the recipe JSON structure
SCHEMA: Dict[str, str] = {"@context": "https://schema.org", "@type": "Recipe"}

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
    keywords: List[str] = field(default_factory=list)
    tool: List[str] = field(default_factory=list)
    recipeIngredient: List[str] = field(default_factory=list)
    recipeInstructions: List[dict] = field(default_factory=list)
    nutrition: Dict[str, str] = field(default_factory=dict)
    datePublished: str = ""

    def to_json(self) -> Dict[str, str]:
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

class AbstractRecipeParser(ABC):
    """
    Abstract base class for recipe parsers.
    This class defines the interface for parsing recipes from an AbstractScraper object.
    """

    HEADERS: Dict[str, str] = {}

    def __init__(self, recipe: AbstractScraper):
        """
        Initializes the RecipeParser with a recipe scraper object.
        Args:
            recipe (AbstractScraper): The recipe scraper object containing raw recipe data.
        """
        self.recipe = recipe

    @abstractmethod
    def parse_recipe(self) -> 'RecipeForCookBook':
        """
        Parses a recipe from an AbstractScraper object.

        Returns:
            RecipeForCookBook: A formatted recipe object ready for saving.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

class DefaultRecipeParser(AbstractRecipeParser):
    """Default parser for recipes."""

    # Reasonable default UA so trivial bot-blocks don’t trigger on unknown hosts.
    HEADERS: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) "
            "Gecko/20100101 Firefox/139.0"
        ),
    }

    def parse_recipe(self) -> 'RecipeForCookBook':
        """
        Parses a recipe from an AbstractScraper object.
        Extracts relevant data and formats it into a `RecipeForCookBook` object.
        """
        cookbook_recipe = RecipeForCookBook(
            name=self.recipe.title(),
            author=self.recipe.author(),
            recipeYield=self.recipe.yields(),
            description=self.recipe.description(),
            url=self.recipe.url,
            image=self.recipe.to_json().get("image", ""),
            totalTime=self.recipe.schema.data.get("totalTime", ""),
            prepTime=self.recipe.schema.data.get("prepTime", ""),
            cookTime=self.recipe.schema.data.get("cookTime", ""),
            recipeCategory=self.recipe.category(),
            keywords=self.recipe.keywords() + self.recipe.dietary_restrictions(),
            tool=[],
            recipeIngredient=self.recipe.ingredients(),
            recipeInstructions=self.recipe.schema.data.get("recipeInstructions", []),
            nutrition=self.recipe.nutrients(),
            datePublished=self.recipe.schema.data.get("datePublished", ""),
        )
        try:
            cuisine = self.recipe.cuisine()
        except Exception:
            cuisine = None
        if cuisine:
            cookbook_recipe.keywords.append(cuisine)

        return cookbook_recipe

class AlbertHeijnRecipeParser(DefaultRecipeParser):
    """Parser for Albert Heijn recipes."""

    # Headers closely matching a real Firefox request (helps prevent 403).
    HEADERS: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
            "Gecko/20100101 Firefox/122.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "nl,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-GPC": "1",
        "Priority": "u=0, i",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

    def parse_recipe(self) -> 'RecipeForCookBook':
        """
        Parses a recipe from an Albert Heijn recipe scraper object.
        Extracts relevant data and formats it into a `RecipeForCookBook` object.
        """
        cookbook_recipe = super().parse_recipe()
        # Tool list (appliances) – be defensive if soup is missing.
        try:
            apps = self.recipe.soup.find_all("ul", {"data-testhook": "appliances"})
            cookbook_recipe.tool = [a.string for a in apps if getattr(a, "string", None)]
        except Exception:
            cookbook_recipe.tool = []
        # Yields might be "4 porties" / "4 servings" -> coerce to int if possible
        try:
            y = self.recipe.yields()
            if isinstance(y, str):
                num = y.split()[0]
                cookbook_recipe.recipeYield = int(num)
        except Exception:
            pass
        return cookbook_recipe

HOST_PARSER_MAPPING: Dict[str, type[AbstractRecipeParser]] = {
    "www.ah.nl": AlbertHeijnRecipeParser,
}

def get_proper_parser(url: str) -> type[AbstractRecipeParser]:
    """
    Returns the appropriate parser class for the given URL based on its host.
    """
    host = urlparse(url).hostname or ""
    return HOST_PARSER_MAPPING.get(host, DefaultRecipeParser)

def parse_recipe(recipe: AbstractScraper) -> RecipeForCookBook:
    """
    Parses a recipe using the appropriate parser based on the recipe's host.
    """
    parser_class = get_proper_parser(recipe.url)
    recipe_parser = parser_class(recipe=recipe)
    return recipe_parser.parse_recipe()

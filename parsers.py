from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from functools import cached_property
from urllib.parse import urlparse

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


class AbstractRecipeParser(ABC):
    """    Abstract base class for recipe parsers.
    This class defines the interface for parsing recipes from an AbstractScraper object.
    Attributes:
        recipe (AbstractScraper): The recipe scraper object containing raw recipe data.
    """

    HEADERS = {}

    def __init__(self, recipe: AbstractScraper):
        """
        Initializes the RecipeParser with a recipe scraper object.
        Args:
            recipe (AbstractScraper): The recipe scraper object containing raw recipe data.
        """
        self.recipe = recipe

    @abstractmethod
    def parse_recipe(self) -> RecipeForCookBook:
        """
        Parses a recipe from an AbstractScraper object.

        Returns:
            RecipeForCookBook: A formatted recipe object ready for saving.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")


class DefaultRecipeParser(AbstractRecipeParser):
    """    Default parser for recipes.
    Inherits from RecipeParser and implements the parse_recipe method.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
    }  # HTTP headers for web requests

    def parse_recipe(self) -> RecipeForCookBook:
        """
        Parses a recipe from an AbstractScraper object.
        Extracts relevant data and formats it into a `RecipeForCookBook` object.
        This method retrieves various attributes from the recipe object and constructs a `RecipeForCookBook` instance.
        It includes the recipe's name, author, yield, description, URL, image, times, category, keywords,
        tools, ingredients, instructions, nutrition, and publication date.
        The method also handles optional attributes like cuisine and dietary restrictions.
        It does not include tools or yield in the default implementation, as these are specific to certain parsers.

        :return: A `RecipeForCookBook` object containing the parsed recipe data.
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
            recipeInstructions=self.recipe.schema.data.get('recipeInstructions', []),
            nutrition=self.recipe.nutrients(),
            datePublished=self.recipe.schema.data.get("datePublished", "")
        )
        if self.recipe.cuisine():
            cookbook_recipe.keywords.append(self.recipe.cuisine())

        return cookbook_recipe


class AlbertHeijnRecipeParser(DefaultRecipeParser):
    """    Parser for Albert Heijn recipes.
    Inherits from RecipeParser and implements the parse_recipe method.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
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
        "Cache-Control": "no-cache"
    }

    def parse_recipe(self) -> RecipeForCookBook:
        """
        Parses a recipe from an Albert Heijn recipe scraper object.
        Extracts relevant data and formats it into a `RecipeForCookBook` object.

        Returns:
            RecipeForCookBook: A formatted recipe object ready for saving.
        """
        cookbook_recipe = super().parse_recipe()
        apps = self.recipe.soup.find_all("ul", {"data-testhook": "appliances"})  # Find all tools needed for recipe
        cookbook_recipe.tool = [a.string for a in apps if a.string]  # Extract tool names from the found elements
        cookbook_recipe.recipeYield = int(self.recipe.yields().strip(" servings"))  # Convert yield str to integer
        return cookbook_recipe


HOST_PARSER_MAPPING: dict[str, type[AbstractRecipeParser]] = {
    "www.ah.nl": AlbertHeijnRecipeParser,
}


def get_proper_parser(url: str) -> type[AbstractRecipeParser]:
    """    Returns the appropriate parser class for the given URL based on its host.
    Args:
        url (str): The URL for which to get the parser.
    Returns:
        type[AbstractRecipeParser]: The parser class to use for the request.
    """
    host = urlparse(url).hostname
    if host not in HOST_PARSER_MAPPING:
        print(f"{host} is not yet known, using default parser.")
        return DefaultRecipeParser
    else:
        parser = HOST_PARSER_MAPPING[host]
        print(f"Using {HOST_PARSER_MAPPING[host].__name__} for {host}")
        return parser


def parse_recipe(recipe: AbstractScraper) -> RecipeForCookBook:
    """    Parses a recipe using the appropriate parser based on the recipe's host.
    Args:
        recipe (AbstractScraper): The recipe scraper object containing raw recipe data.
    Returns:
        RecipeForCookBook: A formatted recipe object ready for saving.
    """
    parser = get_proper_parser(recipe.url)  # Ensure the parser is set up for the recipe's host
    recipe_parser = parser(recipe=recipe)
    return recipe_parser.parse_recipe()

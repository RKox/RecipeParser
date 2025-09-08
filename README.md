# Recipe Parser

The Recipe Parser converts recipe web pages or HTML files into a cookbook-ready format. It downloads the recipe, normalises its data, and saves the result (including the image) into a structured directory.

## Prerequisites

- Python 3.11 or later
- `git` installed
- Internet access for downloading recipe pages

## Installation

### Ubuntu / macOS
```bash
# clone the repository
 git clone <repo-url>
 cd RecipeParser

# create and activate a virtual environment
 python3 -m venv venv
 source venv/bin/activate

# install dependencies
 pip install -r requirements.txt
```

### Windows
```powershell
REM clone the repository
git clone <repo-url>
cd RecipeParser

REM create and activate a virtual environment
py -3 -m venv venv
venv\Scripts\activate

REM install dependencies
pip install -r requirements.txt
```

## Finding the right network interface
The parser can bind outgoing requests to a specific network interface. If no interface is provided, it uses `127.0.0.1` by default. Use one of the following commands to discover available interfaces:

- **Ubuntu:** `ip -o link show`
- **macOS:** `networksetup -listallhardwareports`
- **Windows (PowerShell):** `Get-NetAdapter`

Choose the interface name from the output (e.g. `eth0`, `en0`, `Wi-Fi`) and provide it with the `--interface` option.

## Usage
Run the parser via `web_to_cookbook.py`. The most common options are shown below.

```bash
python web_to_cookbook.py [options]
```

| Option | Description |
|--------|-------------|
| `-i`, `--interface` | Network interface to use. Defaults to `127.0.0.1` if omitted. |
| `-u`, `--url` | Recipe URL to scrape. Can be repeated. |
| `-f`, `--file` | File containing recipe URLs or a local HTML file. Can be repeated. |
| `-t`, `--target` | Output folder for parsed recipes. Defaults to `parsed_recipes`. |

### Examples
Parse a single recipe from a URL:
```bash
python web_to_cookbook.py -u "https://example.com/recipe"
```

Parse multiple recipes and save them into `my_recipes`:
```bash
python web_to_cookbook.py -u url1 -u url2 -t my_recipes
```

Parse URLs listed in a file and bind to a specific interface:
```bash
python web_to_cookbook.py -f urls.txt -i eth0
```

On Windows, replace `python` with `py` if needed and quote interface names that include spaces:
```powershell
py web_to_cookbook.py -u https://example.com -i "Wi-Fi"
```

The script creates a subdirectory for each recipe inside the target folder containing `recipe.json` and `full.jpg`.

## Running tests
To ensure the project works correctly after changes, run:
```bash
pytest
```

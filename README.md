# Tuna Scraper

A web scraping toolkit for extracting product information from e-commerce websites, with a focus on tuna products from Carrefour.

## Features

- **HTML Page Analyzer**: Analyzes HTML pages to identify the right selectors for scraping
- **Product Scraper**: Extracts product information using the identified selectors
- **Infinite Scrolling Support**: Uses Selenium to handle infinite scrolling and load all products
- **Price Cleaning**: Removes currency symbols and converts to decimal format
- **Image Downloading**: Downloads product images and saves them locally
- **JSON Export**: Saves product data to a JSON file

## Requirements

- Python 3.8+
- Required packages (install with `uv add`):
  - requests
  - beautifulsoup4
  - selenium (optional, for infinite scrolling)

## Scripts

### check_page.py

This script analyzes HTML pages to identify the right selectors for scraping. It helps you understand the structure of the page and find the best selectors for extracting product information.

```bash
# Analyze a URL and save the HTML for later use
python check_page.py --url "https://www.carrefour.it/spesa-online/condimenti-e-conserve/tonno-e-pesce-in-scatola/tonno-sott-olio/" --save-html carrefour.it_page.html

# Analyze a local HTML file with a specific container class
python check_page.py --html-file carrefour.it_page.html --container-class "product-item"

# Save analysis results to a JSON file
python check_page.py --html-file carrefour.it_page.html --output-file analysis_results.json
```

### scrape_example.py

This script uses the selectors identified by check_page.py to scrape product information from Carrefour. It can handle infinite scrolling and clean up price formats.

```bash
# Scrape products from a URL with infinite scrolling
python scrape_example.py --use-selenium

# Scrape products from a local HTML file
python scrape_example.py --html-file carrefour.it_page.html

# Save product data to a custom file
python scrape_example.py --output-file tuna_products.json
```

### main.py

The main scraper script with additional features like image downloading and robots.txt checking.

```bash
# Scrape products with default settings
python main.py

# Scrape products from a custom URL
python main.py --url "https://www.carrefour.it/spesa-online/condimenti-e-conserve/tonno-e-pesce-in-scatola/tonno-sott-olio/"

# Customize delay between requests
python main.py --min-delay 1.0 --max-delay 3.0

# Save images to a custom directory
python main.py --output-dir "tuna_images"

# Save product data to a custom file
python main.py --output-file "tuna_products.json"

# Set logging level
python main.py --log-level DEBUG
```

## How to Use

1. **Analyze the Page**: Use `check_page.py` to analyze the HTML structure and identify the right selectors for scraping.

2. **Test Scraping**: Use `scrape_example.py` to test scraping with the identified selectors. This script is simpler and focuses on extracting product information.

3. **Full Scraping**: Use `main.py` for full scraping with additional features like image downloading and robots.txt checking.

## Example Workflow

1. Analyze the page structure:
   ```bash
   python check_page.py --url "https://www.carrefour.it/spesa-online/condimenti-e-conserve/tonno-e-pesce-in-scatola/tonno-sott-olio/" --save-html carrefour.it_page.html
   ```

2. Test scraping with the identified selectors:
   ```bash
   python scrape_example.py --html-file carrefour.it_page.html
   ```

3. Run the full scraper with image downloading:
   ```bash
   python main.py
   ```

## Notes

- The scripts include user-agent rotation and request delays to be respectful to the target website.
- Always check the website's robots.txt and terms of service before scraping.
- The scripts are designed to be easily adaptable to other e-commerce websites by changing the selectors.
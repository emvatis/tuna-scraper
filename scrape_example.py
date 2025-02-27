#!/usr/bin/env python3
"""
Example script that uses the selectors identified by check_page.py
to scrape product information from Carrefour.
"""

import argparse
import json
import re
import sys
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# Import functions from main.py
from main import create_session, save_data_json

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


def clean_price(price_str):
    """
    Cleans price string by removing currency symbols and converting to decimal format.

    Args:
        price_str: Price string (e.g. "€ 3,49")

    Returns:
        Cleaned price as float (e.g. 3.49)

    """
    # Remove currency symbols and whitespace
    price_str = re.sub(r"[€$£¥]", "", price_str).strip()

    # Replace comma with period for decimal point
    price_str = price_str.replace(",", ".")

    try:
        return float(price_str)
    except ValueError:
        return None


def scrape_with_selenium(url, scroll_pause_time=1.5, max_scrolls=20):
    """
    Uses Selenium to scrape a page with infinite scrolling.

    Args:
        url: URL to scrape
        scroll_pause_time: Time to pause between scrolls
        max_scrolls: Maximum number of scrolls to perform

    Returns:
        HTML content of the page after scrolling

    """
    if not SELENIUM_AVAILABLE:
        print("Selenium is not installed. Please install it with: pip install selenium")
        print("Proceeding with single page scraping...")
        return None

    print(f"Using Selenium to scrape with infinite scrolling: {url}")

    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(url)

        # Wait for the page to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "product-item")))

        # Get initial product count
        initial_products = len(driver.find_elements(By.CLASS_NAME, "product-item"))
        print(f"Initial product count: {initial_products}")

        # Scroll down to load more products
        last_product_count = initial_products
        scroll_count = 0

        while scroll_count < max_scrolls:
            # Scroll to the bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Wait for new products to load
            time.sleep(scroll_pause_time)

            # Count products
            current_products = len(driver.find_elements(By.CLASS_NAME, "product-item"))
            print(f"Current product count: {current_products}")

            # If no new products were loaded, we've reached the end or hit a loading issue
            if current_products == last_product_count:
                scroll_count += 1
                # Try clicking "Load more" button if it exists
                try:
                    load_more_button = driver.find_element(By.CLASS_NAME, "load-more")
                    if load_more_button.is_displayed():
                        load_more_button.click()
                        time.sleep(scroll_pause_time)
                except:
                    pass
            else:
                # Reset counter if we found new products
                scroll_count = 0
                last_product_count = current_products

        print(f"Final product count: {last_product_count}")

        # Return the page source after scrolling
        return driver.page_source

    finally:
        driver.quit()


def scrape_carrefour_with_selectors(html_file=None, url=None, use_selenium=False):
    """
    Scrapes product data from Carrefour using the selectors identified by check_page.py.

    Args:
        html_file: Path to a local HTML file to scrape
        url: URL to scrape (if html_file is not provided)
        use_selenium: Whether to use Selenium for infinite scrolling

    Returns:
        List of product dictionaries

    """
    if not html_file and not url:
        raise ValueError("Either html_file or url must be provided")

    # Load HTML content
    if html_file:
        print(f"Loading HTML from file: {html_file}")
        with open(html_file, encoding="utf-8") as f:
            html_content = f.read()
        source_url = "Local file"
        base_url = "https://www.carrefour.it"  # Default base URL for local files
    else:
        if use_selenium and SELENIUM_AVAILABLE:
            html_content = scrape_with_selenium(url)
            if not html_content:
                print("Falling back to regular request...")
                session = create_session()
                response = session.get(url, timeout=30)
                response.raise_for_status()
                html_content = response.text
        else:
            print(f"Downloading page: {url}")
            session = create_session()
            response = session.get(url, timeout=30)
            response.raise_for_status()
            html_content = response.text

        source_url = url
        base_url = url.split("/spesa-online")[0] if "/spesa-online" in url else url

    # Parse HTML
    soup = BeautifulSoup(html_content, "html.parser")

    # Find all product items
    items = soup.find_all("div", class_="product-item")
    print(f"Found {len(items)} product items")

    product_list = []

    for item in items:
        try:
            # Extract product name and link
            link_element = item.find("a", class_="product-link")

            if not link_element:
                # Fallback to other potential title elements
                name_element = item.find("div", class_="product-name")
                name = name_element.text.strip() if name_element else "N/A"
                product_url = None
            else:
                name = link_element.text.strip()
                # Get the product URL from the href attribute
                product_url = link_element.get("href")
                if product_url and not product_url.startswith("http"):
                    # Make relative URLs absolute
                    product_url = urljoin(base_url, product_url)

            # Clean up the name (remove extra whitespace)
            name = " ".join(name.split())

            # Extract price
            price_element = item.find("div", class_="price")
            price_text = price_element.text.strip() if price_element else "N/A"

            # The price text contains both unit price and actual price
            # The actual price is usually the last number with € symbol
            # Example: "€ 14,54 al kg/240.0 g € 3,49"
            price_matches = list(re.finditer(r"€\s*(\d+[.,]?\d*)", price_text))

            if price_matches:
                # Get the last match (actual product price)
                raw_price = price_matches[-1].group(0).strip()
                # Clean the price (remove € and convert to decimal)
                price = clean_price(raw_price)
            else:
                price = None

            # Extract image URL
            img_element = item.find("img", class_="tile-image")
            image_url = img_element.get("src") if img_element else None

            # If src is not available, try data-src
            if not image_url and img_element:
                image_url = img_element.get("data-src")

            # Make image URL absolute if it's relative
            if image_url and image_url.startswith("/"):
                image_url = urljoin(base_url, image_url)

            # Extract price per kg/unit
            unit_price_element = item.find("span", class_="unit-price")
            price_per_kg_text = unit_price_element.text.strip() if unit_price_element else "N/A"

            # Clean the unit price
            unit_price_match = re.search(r"€\s*(\d+[.,]?\d*)", price_per_kg_text)
            if unit_price_match:
                unit_price = clean_price(unit_price_match.group(0))
            else:
                unit_price = None

            # Create product dictionary
            product_data = {
                "name": name,
                "price": price,
                "image_url": image_url,
                "price_per_kg": unit_price,
                "product_url": product_url,
                "source_url": source_url,
            }

            product_list.append(product_data)
            print(f"Extracted product: {name[:50]}... - {price}")

        except Exception as e:
            print(f"Error extracting data from item: {e}")

    return product_list


def main():
    parser = argparse.ArgumentParser(description="Example Carrefour scraper using identified selectors")
    parser.add_argument(
        "--url",
        type=str,
        default="https://www.carrefour.it/spesa-online/condimenti-e-conserve/tonno-e-pesce-in-scatola/tonno-sott-olio/",
        help="URL to scrape",
    )
    parser.add_argument("--html-file", type=str, help="Use a local HTML file instead of downloading")
    parser.add_argument("--output-file", type=str, default="products.json", help="File to save product data to")
    parser.add_argument(
        "--use-selenium", action="store_true", help="Use Selenium to handle infinite scrolling (requires selenium package)"
    )

    args = parser.parse_args()

    try:
        # Scrape products
        products = scrape_carrefour_with_selectors(
            html_file=args.html_file, url=None if args.html_file else args.url, use_selenium=args.use_selenium
        )

        if products:
            print(f"\nSuccessfully scraped {len(products)} products")

            # Save data
            save_data_json(products, output_file=args.output_file)

            print("\nScraping completed successfully!")
            print(f"Found {len(products)} products")
            print(f"Product data saved to: {args.output_file}")

            # Print a sample of the data
            print("\nSample product data:")
            if products:
                sample = json.dumps(products[0], indent=2)
                print(sample)
        else:
            print("\nNo products found")
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

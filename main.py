import argparse
import json
import logging
import os
import random
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler(),  # Also log to console
    ],
)
logger = logging.getLogger(__name__)

# Common user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
]


def create_session():
    """
    Creates a requests session with retry logic and a random user agent.
    """
    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=3,  # Maximum number of retries
        backoff_factor=1,  # Time factor between retries
        status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
        allowed_methods=["GET"],  # Only retry for GET requests
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Set a random user agent
    session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    return session


def check_robots_txt(session, base_url):
    """
    Checks robots.txt to see if scraping is allowed.
    """
    parsed_url = urllib.parse.urlparse(base_url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

    try:
        response = session.get(robots_url, timeout=10)
        if response.status_code == 200:
            # Very basic check - in a real implementation, you'd want to use a proper robots.txt parser
            if "Disallow: " + parsed_url.path in response.text:
                logger.warning(f"Scraping {base_url} may not be allowed according to robots.txt")
                return False
        return True
    except Exception as e:
        logger.warning(f"Could not check robots.txt: {e}")
        return True  # Proceed with caution if we can't check


def scrape_carrefour(url, delay_range=(2, 5)):
    """
    Scrapes product data from the Carrefour website.

    Args:
        url: The URL to scrape
        delay_range: Tuple of (min_delay, max_delay) in seconds between requests

    Returns:
        List of product dictionaries or None if an error occurred

    """
    session = create_session()

    # Check robots.txt
    if not check_robots_txt(session, url):
        logger.warning("Proceeding with caution as robots.txt may disallow scraping this URL")

    try:
        # Add a random delay before making the request
        delay = random.uniform(*delay_range)
        logger.info(f"Waiting {delay:.2f} seconds before making request")
        time.sleep(delay)

        logger.info(f"Scraping URL: {url}")
        response = session.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        product_list = []
        # Find all product items
        items = soup.find_all("div", class_="ProductCard__content___1vF38")
        if not items:
            logger.info("Primary selector did not find any items, trying fallback selectors.")
            # Fallback: search for div elements with class containing 'product-card'
            items = soup.find_all("div", class_=lambda x: x and "product-card" in x.lower())
            if not items:
                logger.info("Fallback selector did not find any items, trying article tags.")
                items = soup.find_all("article")
        logger.info(f"Found {len(items)} product items")
        if len(items) == 0:
            logger.info("No HTML product elements found. Trying JSON-LD extraction.")
            json_products = parse_json_ld(soup)
            logger.info(f"Found {len(json_products)} JSON-LD products")
            for prod in json_products:
                name = prod.get("name", "N/A")
                price = "N/A"
                if "offers" in prod and isinstance(prod["offers"], dict):
                    price = prod["offers"].get("price", "N/A")
                image_url = prod.get("image")
                if isinstance(image_url, list):
                    image_url = image_url[0] if image_url else None
                product_data = {
                    "name": name,
                    "price": price,
                    "image_url": image_url,
                    "price_per_kg": "N/A",
                    "source_url": url,
                }
                product_list.append(product_data)
        else:
            logger.info(f"Proceeding with HTML extraction from {len(items)} items")

        for item in items:
            try:
                name = item.find("h3", class_="ProductCard__title___3Rq5w").text.strip()
                price = item.find("span", class_="Price__value___1EyWx").text.strip()

                # Handle case where image might not have src attribute
                img_element = item.find("img", class_="ProductCard__image___2sV_h")
                image_url = img_element.get("src") if img_element else None

                if not image_url:
                    # Try data-src as fallback
                    image_url = img_element.get("data-src") if img_element else None

                # Extract price per kg if available
                price_per_kg_element = item.find("div", class_="ProductCard__unitPrice___3Ym1w")
                price_per_kg = price_per_kg_element.text.strip() if price_per_kg_element else "N/A"

                product_data = {
                    "name": name,
                    "price": price,
                    "image_url": image_url,
                    "price_per_kg": price_per_kg,
                    "source_url": url,
                }
                product_list.append(product_data)
                logger.debug(f"Extracted product: {name}")
            except Exception as e:
                logger.exception(f"Error extracting data from item: {e}")

        return product_list

    except requests.exceptions.RequestException as e:
        logger.exception(f"Request error: {e}")
        return None
    except Exception as e:
        logger.exception(f"General error: {e}")
        return None


def parse_json_ld(soup):
    """
    Extracts product data from JSON-LD script tags.
    """
    products = []
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                if data.get("@type") == "Product":
                    products.append(data)
                elif "itemListElement" in data:
                    for item in data["itemListElement"]:
                        prod = item.get("item")
                        if prod and prod.get("@type") == "Product":
                            products.append(prod)
            elif isinstance(data, list):
                for d in data:
                    if d.get("@type") == "Product":
                        products.append(d)
        except Exception as e:
            logger.debug(f"Error parsing JSON-LD: {e}")
    return products


def save_images(product_list, output_dir="images", session=None, delay_range=(1, 3)):
    """
    Downloads and saves product images.

    Args:
        product_list: List of product dictionaries
        output_dir: Directory to save images to
        session: Requests session to use (creates a new one if None)
        delay_range: Tuple of (min_delay, max_delay) in seconds between requests

    """
    if not session:
        session = create_session()

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    logger.info(f"Saving images to {output_path.absolute()}")

    for i, product in enumerate(product_list):
        try:
            image_url = product.get("image_url")
            if not image_url:
                logger.warning(f"No image URL for product: {product.get('name', 'Unknown')}")
                continue

            # Add a random delay before downloading
            delay = random.uniform(*delay_range)
            logger.info(f"Waiting {delay:.2f} seconds before downloading image")
            time.sleep(delay)

            # Make the request
            response = session.get(image_url, timeout=30)
            response.raise_for_status()

            # Extract image extension from URL or content type
            content_type = response.headers.get("Content-Type", "")
            if "jpeg" in content_type or "jpg" in content_type:
                ext = ".jpg"
            elif "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            elif "webp" in content_type:
                ext = ".webp"
            else:
                # Try to get extension from URL
                url_ext = os.path.splitext(urllib.parse.urlparse(image_url).path)[1]
                ext = url_ext if url_ext else ".jpg"  # Default to jpg if we can't determine

            # Create a safe filename
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in product.get("name", f"product_{i}"))
            safe_name = safe_name[:50]  # Limit filename length
            file_name = output_path / f"{safe_name}{ext}"

            with open(file_name, "wb") as f:
                f.write(response.content)

            # Update product with local image path
            product["local_image_path"] = str(file_name)
            logger.info(f"Saved image: {file_name}")

        except Exception as e:
            logger.exception(f"Error saving image for {product.get('name', 'Unknown')}: {e}")


def save_data_json(product_list, output_file="products.json"):
    """
    Saves product data to a JSON file.

    Args:
        product_list: List of product dictionaries
        output_file: File to save data to

    """
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(product_list, f, indent=4, ensure_ascii=False)
        logger.info(f"Saved data to: {output_file}")
    except Exception as e:
        logger.exception(f"Error saving data to {output_file}: {e}")


def parse_arguments():
    """
    Parses command line arguments.
    """
    parser = argparse.ArgumentParser(description="Carrefour product scraper")
    parser.add_argument(
        "--url",
        type=str,
        default="https://www.carrefour.it/spesa-online/condimenti-e-conserve/tonno-e-pesce-in-scatola/tonno-sott-olio/",
        help="URL to scrape",
    )
    parser.add_argument("--output-dir", type=str, default="images", help="Directory to save images to")
    parser.add_argument("--output-file", type=str, default="products.json", help="File to save product data to")
    parser.add_argument("--min-delay", type=float, default=2.0, help="Minimum delay between requests in seconds")
    parser.add_argument("--max-delay", type=float, default=5.0, help="Maximum delay between requests in seconds")
    parser.add_argument(
        "--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO", help="Logging level"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create a session for reuse
    session = create_session()

    # Scrape products
    products = scrape_carrefour(args.url, delay_range=(args.min_delay, args.max_delay))

    if products:
        logger.info(f"Successfully scraped {len(products)} products")

        # Save data
        save_images(
            products,
            output_dir=args.output_dir,
            session=session,
            delay_range=(args.min_delay / 2, args.max_delay / 2),  # Use shorter delays for images
        )
        save_data_json(products, output_file=args.output_file)

        print("\nScraping completed successfully!")
        print(f"Found {len(products)} products")
        print(f"Images saved to: {args.output_dir}/")
        print(f"Product data saved to: {args.output_file}")
        print("Log output saved to: scraper.log")
    else:
        logger.error("Failed to scrape products")
        print("\nScraping failed. Check scraper.log for details.")

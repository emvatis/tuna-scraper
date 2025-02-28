import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import logging
from urllib.parse import urljoin
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_nutrition_table(product_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(product_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    # Locate the correct div containing the nutrition information
    nutrition_div = soup.find("div", id="panel-nutritionInfo")
    if not nutrition_div:
        return None

    table_rows = nutrition_div.find_all("div", class_="table-row")
    nutrition_data = {}

    # Extract headers dynamically
    header_columns = table_rows[0].find_all("span")
    headers = [col.text.strip() for col in header_columns if col.text.strip()]

    for row in table_rows[1:]:  # Skip header row
        columns = row.find_all("span")
        if len(columns) >= 2:  # Ensure at least two columns
            nutrient = columns[0].text.strip()
            values = [col.text.strip() for col in columns[1:]]
            nutrition_data[nutrient] = {headers[i]: values[i] for i in range(len(values))}

    return nutrition_data


def download_carousel_images(product_url, save_folder="images"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(product_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    # Locate the alternative images section
    carousel_div = soup.find("div", class_="alternative-images")
    if not carousel_div:
        return "No image carousel found."

    images = carousel_div.find_all("img", class_="js-thumb-img")
    if not images:
        return "No images found in carousel."

    folder_path = Path(save_folder)
    folder_path.mkdir(parents=True, exist_ok=True)

    image_urls = []
    for img in images:
        image_url = img.get("data-src") or img.get("src")  # Prefer data-src if available
        if image_url:
            full_image_url = urljoin(product_url, image_url)
            image_urls.append(full_image_url)

            # Download image
            image_name = Path(full_image_url).name.split("?")[0]  # Remove URL params
            image_path = folder_path.joinpath(image_name)
            with image_path.open("wb") as f:
                f.write(requests.get(full_image_url, headers=headers).content)

    return f"Downloaded {len(image_urls)} images to {save_folder}"


def process_products():
    # Open and load products.json from the carrefour folder
    products_json_path = Path("carrefour") / "products.json"
    with products_json_path.open("r", encoding="utf-8") as f:
        products = json.load(f)

    for product in products:
        product_url = product.get("product_url")
        if not product_url:
            continue
        # Extract barcode from product_url (assumes barcode is the numeric part before the .html)
        barcode = product_url.rstrip("/").split("/")[-1].split(".")[0]

        # Create a directory named after the barcode in the same directory as this script
        product_dir = Path(__file__).resolve().parent / barcode
        product_dir.mkdir(parents=True, exist_ok=True)

        # Get nutritional info and save it as a JSON file in the product directory
        nutrition = get_nutrition_table(product_url)
        if nutrition is not None:
            nutrition_path = product_dir / "nutrition.json"
            with nutrition_path.open("w", encoding="utf-8") as nf:
                json.dump(nutrition, nf, ensure_ascii=False, indent=2)
        else:
            logging.warning(f"Nutritional info not found for {barcode}.")

        # Download carousel images into a subdirectory called "images" inside the barcode folder
        images_folder = product_dir / "images"
        result = download_carousel_images(product_url, save_folder=str(images_folder))
        logging.info(f"Processed product {barcode}: {result}")


if __name__ == "__main__":
    process_products()

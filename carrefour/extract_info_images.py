import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from urllib.parse import urljoin


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

    os.makedirs(save_folder, exist_ok=True)

    image_urls = []
    for img in images:
        image_url = img.get("data-src") or img.get("src")  # Prefer data-src if available
        if image_url:
            full_image_url = urljoin(product_url, image_url)
            image_urls.append(full_image_url)

            # Download image
            image_name = os.path.basename(full_image_url).split("?")[0]  # Remove URL params
            image_path = os.path.join(save_folder, image_name)

            with open(image_path, "wb") as f:
                f.write(requests.get(full_image_url, headers=headers).content)

    return f"Downloaded {len(image_urls)} images to {save_folder}"

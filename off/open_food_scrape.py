import argparse
import logging
import re
import urllib.request
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_high_res_image_url(image_url: str) -> str:
    """Convert Open Food Facts image URLs to full resolution."""
    if not image_url:
        return ""

    # Replace any `.XX.400.jpg` or similar patterns with `.XX.full.jpg`
    return re.sub(r"(\.\d+)\.\d+\.jpg$", r"\1.full.jpg", image_url)


def download_image(image_url: str, filename: str, directory: Path) -> Path | None:
    if image_url.startswith(("http://", "https://")):
        filepath = directory / filename
        try:
            urllib.request.urlretrieve(image_url, filepath)
            logger.info("Image downloaded: %s", filepath)
        except Exception:
            logger.exception("Error downloading image %s", filename)
        else:
            return filepath
    return None


def parse_nutrition_table(soup: BeautifulSoup) -> tuple[list[str], list[list[str]]]:
    """
    Extract headers and rows from the nutrition facts table under #panel_nutrition_facts_table.

    Joins multiple strings in a cell with a space.
    """
    table = soup.select_one("#panel_nutrition_facts_table table")
    if not table:
        return [], []

    headers = [th.get_text(separator=" ", strip=True) for th in table.select("thead th")]
    rows_data = []
    for row in table.select("tbody tr"):
        cells = [td.get_text(separator=" ", strip=True) for td in row.select("td")]
        rows_data.append(cells)
    return headers, rows_data


def format_table(headers: list[str], rows_data: list[list[str]]) -> str:
    """Return a nicely aligned text table from headers and row data."""
    if not headers or not rows_data:
        return "No table data found."
    col_widths = []
    for col_idx in range(len(headers)):
        widest_in_rows = max(len(row[col_idx]) for row in rows_data)
        col_widths.append(max(widest_in_rows, len(headers[col_idx])))
    header_line = " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers)))
    separator = "-+-".join("-" * w for w in col_widths)
    lines = [header_line, separator]
    for row in rows_data:
        line = " | ".join(row[i].ljust(col_widths[i]) for i in range(len(headers)))
        lines.append(line)
    return "\n".join(lines)


def scrape_product(barcode: str) -> BeautifulSoup:
    url = f"https://it.openfoodfacts.org/product/{barcode}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    html_content = response.text

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove unwanted alert boxes from the page.
    for alert in soup.select("div.alert-box.info"):
        alert.decompose()

    product_name_el = soup.select_one("#product > div > div > div.card-section > div > div.medium-8.small-12.columns > h2")
    product_name = product_name_el.text.strip() if product_name_el else "Product Name Not Found"
    logger.info("Product Name: %s", product_name)

    barcode_el = soup.find("span", {"id": "barcode"})
    barcode_found = barcode_el.text.strip() if barcode_el else "Barcode Not Found"
    logger.info("Barcode: %s", barcode_found)

    # Create directory based on barcode.
    image_dir = Path(barcode_found)
    image_dir.mkdir(parents=True, exist_ok=True)

    # Parse nutrition table.
    headers, rows = parse_nutrition_table(soup)
    if headers and rows:
        formatted_table = format_table(headers, rows)
        logger.info("Valori Nutrizionali (as table):\n%s", formatted_table)
    else:
        formatted_table = "No nutrition data found."
        logger.info("Nutrition facts section not found or empty.")

    front_image_tag = soup.select_one("#image_box_front img")
    front_image_url = front_image_tag["src"] if front_image_tag and front_image_tag.has_attr("src") else ""
    logger.info("Front Image URL: %s", front_image_url)
    front_image_url_hq = get_high_res_image_url(front_image_url)

    nutrition_image_tag = soup.select_one("#image_box_nutrition img")
    nutrition_image_url = nutrition_image_tag["src"] if nutrition_image_tag and nutrition_image_tag.has_attr("src") else ""
    if nutrition_image_url:
        logger.info("Nutrition Image URL: %s", nutrition_image_url)
        nutrition_image_url_hq = get_high_res_image_url(nutrition_image_url)
    else:
        logger.info("Nutrition Image not found.")

    ingredients_image_tag = soup.select_one("#image_box_ingredients img")
    ingredients_image_url = ingredients_image_tag.get("src", "") if ingredients_image_tag else ""
    if ingredients_image_url:
        logger.info("Ingredients Image URL: %s", ingredients_image_url)
        ingredients_image_url_hq = get_high_res_image_url(ingredients_image_url)
    else:
        logger.info("Ingredients Image not found.")

    short_product_name = product_name.split(" - ")[0].replace(" ", "_").replace("'", "")[:20]

    download_image(front_image_url_hq, f"{short_product_name}_front.jpg", image_dir)
    download_image(nutrition_image_url_hq, f"{short_product_name}_nutrition.jpg", image_dir)
    ingredients_path = (
        download_image(ingredients_image_url_hq, f"{short_product_name}_ingredients.jpg", image_dir)
        if ingredients_image_url
        else None
    )

    compact_text = f"Product Name: {product_name}\nBarcode: {barcode_found}\n\nNutrition Facts:\n{formatted_table}\n\n"
    if ingredients_path:
        compact_text += f"Ingredients Image: {ingredients_path}\n"
    compact_text = re.sub(r"\n\s*\n+", "\n", compact_text)

    text_file = image_dir / "product_info.txt"
    text_file.write_text(compact_text, encoding="utf-8")
    logger.info("Text saved to: %s", text_file)

    logger.info("Scraping complete.")
    return soup


def main():
    parser = argparse.ArgumentParser(description="Scrape product data from Open Food Facts.")
    parser.add_argument("--barcode", help="Product barcode (e.g., 8004030105096)")
    args = parser.parse_args()
    scrape_product(args.barcode)


if __name__ == "__main__":
    main()

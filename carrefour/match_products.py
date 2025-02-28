#!/usr/bin/env python3
import json
import logging
import re
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def match_products():
    """
    Match product info from products_info.json with product details from products.json.

    Computet otal weight, total protein and protein per euro.

    Returns:
        list: A list of dictionaries containing merged product data.

    """
    try:
        info_path = Path("carrefour/products_info.json")
        prod_path = Path("carrefour/products.json")

        logging.info(f"Loading product info from {info_path}")
        with info_path.open("r", encoding="utf-8") as finfo:
            products_info = json.load(finfo)

        logging.info(f"Loading products from {prod_path}")
        with prod_path.open("r", encoding="utf-8") as fprod:
            products = json.load(fprod)
    except Exception:
        logging.exception("Error loading JSON files")
        return []

    matched = []
    for pinfo in products_info:
        barcode = pinfo.get("barcode")
        num_containers = pinfo.get("num_containers", 1)

        # Group nutritional information by type ('drained' or 'full')
        nutritional = {}
        for entry in pinfo.get("nutritional_information", []):
            ntype = entry.get("type", "unknown")
            nutritional[ntype] = {"protein_grams": entry.get("protein_grams"), "per_grams": entry.get("per_grams")}

        # Prefer drained weight and nutritional info; else use full
        if pinfo.get("drained_weight_per_container_grams") is not None and "drained" in nutritional:
            total_weight = pinfo["drained_weight_per_container_grams"] * num_containers
            protein_info = nutritional["drained"]
        elif pinfo.get("weight_per_container_grams") is not None and "full" in nutritional:
            total_weight = pinfo["weight_per_container_grams"] * num_containers
            protein_info = nutritional["full"]
        else:
            total_weight = pinfo.get("weight_per_container_grams", 0) * num_containers
            protein_info = nutritional.get("full", {})

        # Calculate total protein in grams using protein info per 100g
        protein_per_100 = protein_info.get("protein_grams", 0)
        total_protein = (protein_per_100 * total_weight) / 100 if total_weight else 0

        # Find matching product in products.json by comparing barcode extracted from URL
        for prod in products:
            product_url = prod.get("product_url", "")
            match_obj = re.search(r"/(\d+)\.html$", product_url)
            if match_obj and match_obj.group(1) == barcode:
                price = prod.get("price", 0)
                protein_per_euro = total_protein / price if price > 0 else 0
                combined = {
                    "barcode": barcode,
                    "name": prod.get("name"),
                    "price": price,
                    "total_weight_grams": total_weight,
                    "num_containers": num_containers,
                    "nutritional_information": nutritional,
                    "total_protein_grams": total_protein,
                    "protein_per_euro": round(protein_per_euro, 2),
                }
                matched.append(combined)
                break
    logging.info("Matching completed. Total matched products: %d", len(matched))
    return matched


def save_json(data, output_path) -> None:
    """Save data as JSON to the specified output path."""
    try:
        out_path = Path(output_path)
        if not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fout:
            json.dump(data, fout, ensure_ascii=False, indent=2)
        logging.info("JSON output successfully saved to %s", output_path)
    except Exception:
        logging.exception("Error saving JSON file")


def main() -> None:
    combined_products = match_products()
    output_file = "carrefour/matched_products.json"
    save_json(combined_products, output_file)


if __name__ == "__main__":
    main()

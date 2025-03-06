import json
import logging
import os
from pathlib import Path

import gemini_schema
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def read_images(image_dir: str) -> list[types.Part]:
    """Read all JPG images from the specified directory."""
    image_parts = []
    image_dir_path = Path(image_dir)

    try:
        for image_path in image_dir_path.glob("*.jpg"):
            try:
                image_data = types.Part.from_bytes(data=image_path.read_bytes(), mime_type="image/jpeg")
                image_parts.append(image_data)
                logging.info(f"Successfully read image: {image_path}")
            except Exception:
                logging.exception(f"Error reading image {image_path}")
    except Exception:
        logging.exception(f"Error accessing image directory {image_dir}")

    return image_parts


def read_text_file(text_file_path: str) -> str:
    """Read content from the specified text file."""
    try:
        with Path(text_file_path).open(encoding="utf-8") as f:
            content = f.read()
        logging.info(f"Successfully read text file: {text_file_path}")
    except FileNotFoundError:
        logging.warning(f"Text file not found: {text_file_path}. Returning empty string.")
        return ""
    except Exception:
        logging.exception(f"Error reading text file {text_file_path}")
        return ""
    else:
        return content


def save_response(response_json: dict, image_dir: str) -> None:
    """Save the response as a JSON file with appropriate naming."""
    try:
        barcode = response_json.get("barcode", "result")
        num_containers = response_json.get("num_containers")
        weight = response_json.get("weight_per_container_grams")
        filename = f"{barcode}.json" if weight is None else f"{barcode}_{num_containers}_{weight}.json"

        output_dir = Path(image_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / filename

        with file_path.open("w", encoding="utf-8") as json_file:
            json.dump(response_json, json_file, indent=4)
        logging.info(f"JSON response saved to {file_path}")
    except Exception:
        logging.exception("Error saving JSON response")


def send_prompt_with_images(image_dir: str, text_file_path: str, user_prompt: str, system_prompt: str) -> None:
    """Send prompt with images and text to Gemini API and process the structured response."""
    try:
        # Initialize Gemini API client
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Prepare content
        image_parts = read_images(image_dir)
        text_content = read_text_file(text_file_path)
        full_prompt = f"{system_prompt}\n{user_prompt}\n{text_content}"
        contents = [full_prompt, *image_parts]

        # Send structured prompt
        response = gemini_schema.send_structured_prompt(client=client, model="gemini-2.0-flash", contents=contents)
        logging.info("Prompt sent to Gemini with structured output configuration.")

        # Process structured response
        if not hasattr(response, "candidates") or not response.candidates:
            logging.error("No response candidates found")
            return

        try:
            response_json = response.parsed
            logging.info("Successfully parsed structured response")

            if not response_json or not hasattr(response_json, "barcode"):
                logging.error("Response missing required 'barcode' field")
                return

            # Convert Pydantic model to dict
            try:
                response_dict = response_json.model_dump()  # Pydantic v2
            except AttributeError:
                response_dict = response_json.dict()  # Pydantic v1 fallback

            logging.info(f"Structured response JSON: {json.dumps(response_dict, indent=2)}")
            save_response(response_dict, image_dir)

        except Exception:
            logging.exception("Error processing structured response")

    except Exception:
        logging.exception("Error sending prompt to Gemini")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send prompt with images to Gemini API")
    parser.add_argument("--barcode", default="8004030656031", help="Barcode of the product")
    args = parser.parse_args()

    barcode = args.barcode
    image_directory = barcode
    text_file = f"{barcode}/product_info.txt"

    user_prompt_text = (
        "Describe the product shown in the images, using the provided product information, "
        "for the nutrition facts, check the images first (ground truth). "
        "IMPORTANT: Pay attention to the drained and non-drained weights; not all facts are per 100g. "
        "IMPORTANT: Look for an 'X' sign in the photos, which probably means multiple packages! "
        "IMPORTANT: From the images, you can sometimes tell how many packages there are; cans are "
        "normally round, outlines can help!"
    )

    system_prompt_text = """
    Please extract information about the canned tuna product shown in the images and text file.
    Follow these instructions carefully:
    - Use the images as the primary source (ground truth) for nutritional facts, weights, and number of containers.
    - Check the text file for additional context, but prioritize image data if there's a conflict.
    - Pay attention to drained vs. undrained weights; not all facts are per 100g.
    - Look for an 'X' sign in the photos, which likely indicates multiple packages (e.g., 4 cans).
    - Count the number of containers by examining outlines (e.g., round shapes for cans) in the images if possible.
    - 1 package can have many containers!
    - If single package, use 1 and the weight.
    - Extract ingredients directly from the images or text if present; do not leave as null unless no data is found.
    - For nutritional information, use the values shown in the images and specify if they are for 'drained' or 'full' product.
    - Include manufacturer and production location if visible; distinguish between them carefully.
    - If no data is available for a field, leave it as null, but try to infer reasonable values from the images first.
    """

    logging.info(f"Processing barcode {barcode} with structured output")
    send_prompt_with_images(image_directory, text_file, user_prompt_text, system_prompt_text)

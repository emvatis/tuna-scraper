import json
import logging
import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def read_images(image_dir: str) -> List[types.Part]:
    """Read all JPG images from the specified directory."""
    image_parts = []
    image_dir_path = Path(image_dir)

    try:
        for image_path in image_dir_path.glob("*.jpg"):
            try:
                image_data = types.Part.from_bytes(data=image_path.read_bytes(), mime_type="image/jpeg")
                image_parts.append(image_data)
                logging.info(f"Successfully read image: {image_path}")
            except FileNotFoundError:
                logging.warning(f"Image file not found: {image_path}. Skipping.")
            except Exception as e:
                logging.error(f"Error reading image {image_path}: {e}")
    except Exception as e:
        logging.error(f"Error accessing image directory {image_dir}: {e}")

    return image_parts


def read_text_file(text_file_path: str) -> str:
    """Read content from the specified text file."""
    try:
        with open(text_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        logging.info(f"Successfully read text file: {text_file_path}")
        return content
    except FileNotFoundError:
        logging.warning(f"Text file not found: {text_file_path}. Using empty string.")
        return ""
    except Exception as e:
        logging.error(f"Error reading text file {text_file_path}: {e}")
        return ""


def save_response(response_json: dict, image_dir: str) -> None:
    """Save the response as a JSON file with appropriate naming."""
    try:
        barcode = response_json.get("barcode", "result")
        weight = response_json.get("weight_per_container_grams")
        filename = f"{barcode}.json" if weight is None else f"{barcode}_1_{weight}.json"

        output_dir = Path(image_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / filename

        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump(response_json, json_file, indent=4)
        logging.info(f"JSON response saved to {file_path}")
    except Exception as e:
        logging.error(f"Error saving JSON response: {e}")


def send_prompt_with_images(image_dir: str, text_file_path: str, user_prompt: str, system_prompt: str) -> None:
    """Send prompt with images and text to Gemini API and process the response."""
    try:
        # Initialize Gemini API client
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Prepare content
        image_parts = read_images(image_dir)
        text_content = read_text_file(text_file_path)
        full_prompt = f"{system_prompt}\n{user_prompt}\n{text_content}"
        contents = [full_prompt] + image_parts

        # Send request to Gemini
        response = client.models.generate_content(model="gemini-2.0-flash", contents=contents)
        logging.info("Prompt sent to Gemini successfully.")

        # Process response
        if not hasattr(response, "candidates") or not response.candidates:
            logging.error("No response candidates found")
            return

        try:
            response_text = response.candidates[0].content.parts[0].text
            logging.info(f"Raw response: {response_text}")

            if not response_text.strip():
                logging.error("Received empty response; skipping JSON saving.")
                return

            # Strip markdown ```json tags if present
            cleaned_response = response_text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]  # Remove ```json
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]  # Remove ```
            cleaned_response = cleaned_response.strip()

            response_json = json.loads(cleaned_response)
            if "barcode" not in response_json:
                logging.error("Response missing required 'barcode' field")
                return

            save_response(response_json, image_dir)

        except (IndexError, AttributeError) as e:
            logging.error(f"Failed to extract response text: {e}")
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON response after cleaning: {e}")
            logging.error(f"Cleaned response: {cleaned_response}")

    except Exception as e:
        logging.error(f"Error sending prompt to Gemini: {e}")


if __name__ == "__main__":
    image_directory = "8002330026868"
    text_file = "8002330026868/product_info.txt"
    user_prompt_text = (
        "Describe the product shown in the images, using the provided product information, "
        "for the nutrition facts, check the images first (ground truth). IMPORTANT: "
        "Pay attention to the drained and non drained. Sometimes not every facts are per 100g."
    )
    system_prompt_text = """
    {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Canned Tuna Product Information",
        "description": "Schema for representing information about a canned tuna product.",
        "type": "object",
        "properties": {
            "barcode": {
                "type": "string",
                "description": "The product's barcode (e.g., EAN-13). Acts as the primary identifier.",
                "pattern": "^[0-9]{8,14}$"
            },
            "product_name": {
                "type": "string",
                "description": "The name of the canned tuna product (e.g., Yellowfin Tuna in Olive Oil)"
            },
            "ingredients": {
                "type": "string",
                "description": "A comma-separated list of ingredients."
            },
            "num_containers": {
                "type": "integer",
                "description": "Number of individual cans/containers in the package"
            },
            "weight_per_container_grams": {
                "type": "number",
                "description": "The weight of each container in grams (e.g., 80.0)"
            },
            "drained_weight_per_container_grams": {
                "type": "number",
                "description": "The drained weight of the product per container in grams (e.g., 52.0)"
            },
            "nutritional_information": {
                "type": "array",
                "description": "Array of nutritional information entries.",
                "items": {
                    "type": "object",
                    "properties": {
                        "per_grams": {
                            "type": "number",
                            "description": "The amount in grams the nutritional information is based on (e.g., 100)"
                        },
                        "type": {
                            "type": "string",
                            "description": "The state of the product (e.g., drained, full)",
                            "enum": ["drained", "full"]
                        },
                        "energy_kcal": {
                            "type": "number",
                            "description": "Energy in kilocalories (kcal)"
                        },
                        "fat_grams": {
                            "type": "number",
                            "description": "Fat content in grams (g)"
                        },
                        "saturated_fat_grams": {
                            "type": "number",
                            "description": "Saturated fat content in grams (g)"
                        },
                        "protein_grams": {
                            "type": "number",
                            "description": "Protein content in grams (g)"
                        },
                        "salt_grams": {
                            "type": "number",
                            "description": "Salt content in grams (g)"
                        }
                    },
                    "required": [
                        "per_grams",
                        "type",
                        "energy_kcal",
                        "fat_grams",
                        "saturated_fat_grams",
                        "protein_grams",
                        "salt_grams"
                    ]
                }
            },
            "other_information": {
                "type": "object",
                "description": "Additional information about the product.",
                "properties": {
                    "portions_per_container": {
                        "type": "integer",
                        "description": "Number of portions per container."
                    },
                    "dietary_advice": {
                        "type": "string",
                        "description": "Dietary advice for the product.",
                        "nullable": true
                    }
                },
                "required": []
            },
            "manufacturer": {
                "type": "string",
                "description": "The name of the manufacturer."
            },
            "produced_in": {
                "type": "string",
                "description": "The country where the product was produced."
            },
            "customer_service_number": {
                "type": "string",
                "description": "The customer service number.",
                "nullable": true
            }
        },
        "required": ["barcode"]
    }

    This is the schema I would like you to follow when I ask for extraction of info. 
    Also make your output downloadable as json with the name the same as the barcode please. 
    If single package just use 1 and the weight.
    """

    send_prompt_with_images(image_directory, text_file, user_prompt_text, system_prompt_text)

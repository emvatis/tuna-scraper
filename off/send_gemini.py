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
            except FileNotFoundError:
                logging.warning(f"Image file not found: {image_path}. Skipping.")
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
        logging.warning(f"Text file not found: {text_file_path}. Using empty string.")
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


def send_prompt_with_images(
    image_dir: str, text_file_path: str, user_prompt: str, system_prompt: str, use_structured_output: bool = True
) -> None:
    """Send prompt with images and text to Gemini API and process the response."""
    try:
        # Initialize Gemini API client
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Prepare content
        image_parts = read_images(image_dir)
        text_content = read_text_file(text_file_path)
        full_prompt = f"{system_prompt}\n{user_prompt}\n{text_content}"
        contents = [full_prompt, *image_parts]

        if use_structured_output:
            # Use structured output with schema
            response = gemini_schema.send_structured_prompt(client=client, model="gemini-2.0-flash", contents=contents)
            logging.info("Prompt sent to Gemini with structured output configuration.")

            # Process structured response
            if not hasattr(response, "candidates") or not response.candidates:
                logging.error("No response candidates found")
                return

            try:
                # The response is already structured as a JSON object
                response_json = response.parsed
                logging.info("Successfully parsed structured response")

                if not response_json or not hasattr(response_json, "barcode"):
                    logging.error("Response missing required 'barcode' field")
                    return

                # Convert Pydantic model to dict for saving
                # Use model_dump() for Pydantic v2 (dict() is deprecated)
                try:
                    # Try model_dump() first (Pydantic v2)
                    response_dict = response_json.model_dump()
                except AttributeError:
                    # Fall back to dict() for Pydantic v1
                    response_dict = response_json.dict()

                # Log the response JSON
                logging.info(f"Structured response JSON: {json.dumps(response_dict, indent=2)}")

                save_response(response_dict, image_dir)

            except Exception as e:
                logging.exception(f"Error processing structured response: {e}")
                # Fallback to text response if structured parsing fails
                try:
                    response_text = response.text
                    logging.info(f"Falling back to text response: {response_text}")
                    response_dict = json.loads(response_text)
                    save_response(response_dict, image_dir)
                except Exception:
                    logging.exception("Failed to process response even as text")
        else:
            # Use original unstructured output approach
            response = client.models.generate_content(model="gemini-2.0-flash", contents=contents)
            logging.info("Prompt sent to Gemini successfully (unstructured).")

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
                cleaned_response = cleaned_response.removeprefix("```json")  # Remove ```json
                cleaned_response = cleaned_response.removesuffix("```")  # Remove ```
                cleaned_response = cleaned_response.strip()

                response_json = json.loads(cleaned_response)
                if "barcode" not in response_json:
                    logging.error("Response missing required 'barcode' field")
                    return

                # Log the response JSON
                logging.info(f"Unstructured response JSON: {json.dumps(response_json, indent=2)}")

                save_response(response_json, image_dir)

            except (IndexError, AttributeError):
                logging.exception("Failed to extract response text")
            except json.JSONDecodeError:
                logging.exception("Invalid JSON response after cleaning")
                logging.exception(f"Cleaned response: {cleaned_response}")

    except Exception:
        logging.exception("Error sending prompt to Gemini")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send prompt with images to Gemini API")
    parser.add_argument("--barcode", default="8004030656031", help="Barcode of the product")
    parser.add_argument("--unstructured", action="store_true", help="Use unstructured output (legacy mode)")
    args = parser.parse_args()

    barcode = args.barcode
    image_directory = barcode
    text_file = f"{barcode}/product_info.txt"
    use_structured_output = not args.unstructured

    user_prompt_text = (
        "Describe the product shown in the images, using the provided product information, "
        "for the nutrition facts, check the images first (ground truth)."
        "IMPORTANT: Pay attention to the drained and non drained weights, sometimes not every facts are per 100g."
        "IMPORTANT: Pay attention in the photos for an X sign. This probably means many packages!"
        "IMPORTANT: From the images you can also sometimes tell how many packages there are, cans are normally round, the outlines can help!"
    )

    # For unstructured output, we need to include the schema in the prompt
    # For structured output, we use the schema from gemini_schema.py
    if not use_structured_output:
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
    else:
        # For structured output, we use a simpler prompt since the schema is defined in code
        system_prompt_text = """
        Please extract information about the canned tuna product shown in the images and text file.
        Follow these instructions carefully:
        - Use the images as the primary source (ground truth) for nutritional facts, weights, and number of containers.
        - Check the text file for additional context, but prioritize image data if there's a conflict.
        - Pay attention to drained vs. undrained weights; not all facts are per 100g.
        - IMPORTANT: Look for an 'X' sign in the photos, which likely indicates multiple packages (e.g., 4 cans).
        - Count the number of containers by examining outlines (e.g., round shapes for cans) in the images if possible.
        - 1 package can have many containers!
        - If single package just use 1 and the weight.
        - Extract ingredients directly from the images or text if present; do not leave as null unless no data is found.
        - For nutritional information, use the values shown in the images and specify if they are for 'drained' or 'full' product.
        - Include manufacturer and production location if visible; distinguish between them carefully.
        - If no data is available for a field, leave it as null, but try to infer reasonable values from the images first.
        """

    logging.info(f"Processing barcode {barcode} with {'structured' if use_structured_output else 'unstructured'} output")
    send_prompt_with_images(image_directory, text_file, user_prompt_text, system_prompt_text, use_structured_output)

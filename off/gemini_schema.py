import enum
from pathlib import Path

from pydantic import BaseModel


class NutritionType(str, enum.Enum):
    """Enum for nutrition information type."""

    DRAINED = "drained"
    FULL = "full"


class NutritionalInformation(BaseModel):
    """Model for nutritional information."""

    per_grams: float
    type: NutritionType
    energy_kcal: float
    fat_grams: float
    saturated_fat_grams: float
    protein_grams: float
    salt_grams: float


class OtherInformation(BaseModel):
    """Model for other product information."""

    portions_per_container: int | None = None
    dietary_advice: str | None = None


class TunaProduct(BaseModel):
    """Model for canned tuna product information."""

    barcode: str
    product_name: str | None = None
    ingredients: str | None = None
    num_containers: int | None = None
    weight_per_container_grams: float | None = None
    drained_weight_per_container_grams: float | None = None
    nutritional_information: list[NutritionalInformation] | None = None
    other_information: OtherInformation | None = None
    manufacturer: str | None = None
    produced_in: str | None = None
    customer_service_number: str | None = None


def get_schema_config():
    """Return the configuration for structured Gemini output."""
    return {
        "response_mime_type": "application/json",
        "response_schema": TunaProduct,
    }


def load_schema_from_json(json_path: str = None):
    """
    Load schema from a JSON file if provided, otherwise return the default schema.

    This allows for customization of the schema without modifying the code.
    """
    if json_path:
        try:
            import json

            schema_path = Path(json_path)
            if schema_path.exists():
                with schema_path.open("r", encoding="utf-8") as f:
                    schema_json = json.load(f)
                return schema_json
            return get_schema_config()
        except Exception as e:
            import logging

            logging.exception(f"Error loading schema from {json_path}: {e}")
            return get_schema_config()
    else:
        return get_schema_config()


def send_structured_prompt(client, model, contents, schema=None):
    """
    Send a prompt to Gemini with structured output configuration.

    Args:
        client: The Gemini client
        model: The model name to use
        contents: The contents to send to the model
        schema: Optional custom schema to use instead of the default TunaProduct

    Returns:
        The structured response from Gemini

    """
    config = get_schema_config()

    # Override schema if provided
    if schema:
        config["response_schema"] = schema

    # Send request to Gemini with structured output configuration
    response = client.models.generate_content(model=model, contents=contents, config=config)

    return response

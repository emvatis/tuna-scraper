import enum
from pathlib import Path

from pydantic import BaseModel, Field


class NutritionType(str, enum.Enum):
    """Enum for nutrition information type."""

    DRAINED = "drained"
    FULL = "full"


class NutritionalInformation(BaseModel):
    """Model for nutritional information."""

    per_grams: float = Field(..., description="The amount in grams the nutritional information is based on (e.g., 100)")
    type: NutritionType = Field(..., description="The state of the product (e.g., drained, full)")
    energy_kcal: float = Field(..., description="Energy in kilocalories (kcal)")
    fat_grams: float = Field(..., description="Fat content in grams (g)")
    saturated_fat_grams: float = Field(..., description="Saturated fat content in grams (g)")
    protein_grams: float = Field(..., description="Protein content in grams (g)")
    salt_grams: float = Field(..., description="Salt content in grams (g)")


class OtherInformation(BaseModel):
    """Model for other product information."""

    portions_per_container: int | None = Field(None, description="Number of portions per container.")
    dietary_advice: str | None = Field(None, description="Dietary advice for the product.")


class TunaProduct(BaseModel):
    """Model for canned tuna product information."""

    barcode: str = Field(
        ..., description="The product's barcode (e.g., EAN-13). Acts as the primary identifier.", pattern="^[0-9]{8,14}$"
    )
    product_name: str | None = Field(
        None, description="The name of the canned tuna product (e.g., Yellowfin Tuna in Olive Oil)"
    )
    ingredients: str | None = Field(None, description="A comma separated list of ingredients.")
    num_containers: int | None = Field(None, description="Number of individual cans/containers in the package")
    weight_per_container_grams: float | None = Field(None, description="The weight of each container in grams (e.g., 80.0)")
    drained_weight_per_container_grams: float | None = Field(
        None, description="The drained weight of the product per container in grams (e.g., 52.0)"
    )
    nutritional_information: list[NutritionalInformation] | None = Field(
        None, description="Array of nutritional information entries."
    )
    other_information: OtherInformation | None = Field(None, description="Additional information about the product.")
    manufacturer: str | None = Field(None, description="The name of the manufacturer.")
    produced_in: str | None = Field(None, description="The country where the product was produced.")
    customer_service_number: str | None = Field(None, description="The customer service number.")


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

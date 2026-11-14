from typing import TypedDict


class RecommendationData(TypedDict):
    recommendation_type: str
    title: str
    description: str
    difficulty_level: str
    estimated_co2_saved: float | None

# CO2 ESTIMATION POLICY:
# Numerical CO2 savings are not currently calculated.
# Material detection alone does not provide sufficient
# information about material weight or verified emissions
# factors. All recommendations therefore use None until
# a validated estimation methodology is implemented.
# Rule-based recommendation database
RECOMMENDATION_RULES: dict[str, list[RecommendationData]] = {

    "BIODEGRADABLE": [
        {
            "recommendation_type": "recycle",
            "title": "Turn Organic Waste into Compost",
            "description": (
                "Separate fruit peels, vegetable scraps, coffee grounds "
                "and other suitable organic waste. Compost them in a "
                "well-ventilated compost bin. Avoid meat, dairy and "
                "contaminated waste in a basic home composting system."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "upcycle",
            "title": "Create Natural Fertilizer for Plants",
            "description": (
                "Convert suitable biodegradable kitchen waste into "
                "compost and use the finished material to enrich garden "
                "soil. Allow the compost to mature before applying it."
            ),
            "difficulty_level": "medium",
            "estimated_co2_saved": None
        }
    ],

    "CARDBOARD": [
        {
            "recommendation_type": "reuse",
            "title": "Reuse Cardboard Packaging",
            "description": (
                "Keep clean and dry cardboard boxes for storage, "
                "moving, packaging or organising household items. "
                "Reuse sturdy boxes before sending them for recycling."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "recycle",
            "title": "Prepare Cardboard for Recycling",
            "description": (
                "Remove plastic wrapping, tape and other non-paper "
                "materials where practical. Flatten clean, dry cardboard "
                "and send it to an appropriate paper recycling facility. "
                "Keep greasy or heavily contaminated cardboard separate."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        }
    ],

    "GLASS": [
        {
            "recommendation_type": "reuse",
            "title": "Repurpose Glass Jars and Bottles",
            "description": (
                "Clean intact glass jars and bottles and reuse them "
                "as storage containers, organisers or decorative items. "
                "Check for cracks and chips before reuse."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "recycle",
            "title": "Send Glass for Proper Recycling",
            "description": (
                "Separate glass containers according to local recycling "
                "guidelines. Keep broken glass safely contained and "
                "clearly separated to prevent injuries during handling."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        }
    ],

    "METAL": [
        {
            "recommendation_type": "recycle",
            "title": "Recycle Metal Cans and Containers",
            "description": (
                "Separate recyclable aluminium and steel cans from "
                "general waste. Empty containers and follow local "
                "scrap collection or metal recycling instructions."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "reuse",
            "title": "Repurpose Safe Metal Containers",
            "description": (
                "Reuse clean, undamaged metal containers for storage "
                "or household organisation. Avoid sharp edges, rusted "
                "surfaces and containers that previously held hazardous "
                "chemicals."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        }
    ],

    "PAPER": [
        {
            "recommendation_type": "reuse",
            "title": "Use Both Sides of Paper",
            "description": (
                "Reuse sheets with one blank side for rough notes, "
                "practice work, sketches or drafts before recycling "
                "the paper."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "recycle",
            "title": "Recycle Clean and Dry Paper",
            "description": (
                "Collect newspapers, notebooks and suitable paper "
                "separately. Keep them dry and free from food, oil "
                "and other contaminants before sending them for "
                "paper recycling."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        }
    ],

    "PLASTIC": [
        {
            "recommendation_type": "reuse",
            "title": "Reuse Suitable Plastic Containers",
            "description": (
                "Reuse clean, undamaged plastic containers for suitable "
                "storage purposes. Check the container's intended use "
                "before using it for food or drinking water."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "recycle",
            "title": "Sort Plastic by Type Before Recycling",
            "description": (
                "Check the plastic identification marking where "
                "available. Empty and clean the item according to "
                "local collection guidelines, then send accepted "
                "plastic to an appropriate recycling facility."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        }
    ]
}


def generate_recommendations(
    material_name: str
) -> list[RecommendationData]:
    """
    Generate rule-based recommendations for a detected material.

    Validates input, normalizes material names and returns
    independent copies of recommendation definitions.
    """

    if not isinstance(material_name, str):
        raise ValueError(
            "Material name must be a string."
        )

    material_key = material_name.strip().upper()

    if not material_key:
        raise ValueError(
            "Material name cannot be empty."
        )

    recommendations = RECOMMENDATION_RULES.get(
        material_key
    )

    if recommendations is None:
        raise ValueError(
            f"No recommendations available for: {material_key}"
        )

    return [
        recommendation.copy()
        for recommendation in recommendations
    ]
from typing import TypedDict


class RecommendationData(TypedDict):
    recommendation_type: str
    title: str
    description: str
    difficulty_level: str
    estimated_co2_saved: float | None


# Rule-based recommendation database
RECOMMENDATION_RULES: dict[str, list[RecommendationData]] = {

    "BIODEGRADABLE": [
        {
            "recommendation_type": "recycle",
            "title": "Turn Organic Waste into Compost",
            "description": (
                "Convert food scraps, fruit peels and other "
                "biodegradable waste into nutrient-rich compost. "
                "Avoid composting contaminated or unsuitable materials."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "upcycle",
            "title": "Create a Home Composting System",
            "description": (
                "Use a suitable composting container to process "
                "organic household waste and produce natural soil "
                "enrichment for plants."
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
                "Reuse cardboard boxes for storage, packaging "
                "or organising household items."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "recycle",
            "title": "Recycle Cardboard",
            "description": (
                "Flatten clean cardboard boxes and send them "
                "to an appropriate paper recycling facility."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        }
    ],

    "GLASS": [
        {
            "recommendation_type": "reuse",
            "title": "Reuse Glass Containers",
            "description": (
                "Clean suitable glass jars and bottles and reuse "
                "them for storage or decoration. Check for cracks "
                "and avoid unsafe food-contact reuse."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "recycle",
            "title": "Recycle Glass",
            "description": (
                "Separate glass waste and send it to a glass "
                "recycling facility. Handle broken glass carefully."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        }
    ],

    "METAL": [
        {
            "recommendation_type": "recycle",
            "title": "Recycle Metal Containers",
            "description": (
                "Separate recyclable metal cans and containers "
                "and send them to an authorised scrap dealer "
                "or metal recycling centre."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "reuse",
            "title": "Reuse Metal Containers",
            "description": (
                "Reuse safe, clean metal containers for storage "
                "or household organisation. Avoid containers "
                "with sharp edges or hazardous residues."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        }
    ],

    "PAPER": [
        {
            "recommendation_type": "reuse",
            "title": "Reuse Waste Paper",
            "description": (
                "Use the unused side of paper sheets for rough "
                "notes, sketches and practice work."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "recycle",
            "title": "Recycle Waste Paper",
            "description": (
                "Collect clean and dry paper separately and "
                "send it to a paper recycling facility."
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
                "Reuse clean, undamaged containers for appropriate "
                "storage purposes. Do not reuse food containers "
                "unless they are designed for repeated food contact."
            ),
            "difficulty_level": "easy",
            "estimated_co2_saved": None
        },
        {
            "recommendation_type": "recycle",
            "title": "Recycle Plastic Waste",
            "description": (
                "Identify the plastic type where possible, clean "
                "the item according to local recycling guidance "
                "and send it to an appropriate recycling facility."
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
    """

    material_key = material_name.strip().upper()

    recommendations = RECOMMENDATION_RULES.get(
        material_key
    )

    if recommendations is None:
        raise ValueError(
            f"No recommendations available for: {material_name}"
        )

    # Return copies so callers cannot modify the rule definitions.
    return [
        recommendation.copy()
        for recommendation in recommendations
    ]
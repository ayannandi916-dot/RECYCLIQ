
import pytest

from app.services.recommendation_service import (
    generate_recommendations,
    RECOMMENDATION_RULES
)


MATERIALS = [
    "BIODEGRADABLE",
    "CARDBOARD",
    "GLASS",
    "METAL",
    "PAPER",
    "PLASTIC"
]

VALID_TYPES = {"reuse", "repair", "recycle", "upcycle"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


# 1. Every supported material returns recommendations
@pytest.mark.parametrize("material", MATERIALS)
def test_recommendations_exist_for_all_materials(material):
    recommendations = generate_recommendations(material)

    assert len(recommendations) > 0


# 2. Every material has exactly two recommendations
@pytest.mark.parametrize("material", MATERIALS)
def test_exactly_two_recommendations(material):
    recommendations = generate_recommendations(material)

    assert len(recommendations) == 2


# 3. All recommendation types are valid
@pytest.mark.parametrize("material", MATERIALS)
def test_recommendation_types_are_valid(material):
    recommendations = generate_recommendations(material)

    for recommendation in recommendations:
        assert recommendation["recommendation_type"] in VALID_TYPES


# 4. All difficulty levels are valid
@pytest.mark.parametrize("material", MATERIALS)
def test_difficulty_levels_are_valid(material):
    recommendations = generate_recommendations(material)

    for recommendation in recommendations:
        assert recommendation["difficulty_level"] in VALID_DIFFICULTIES


# 5. Every recommendation has required fields
@pytest.mark.parametrize("material", MATERIALS)
def test_required_fields_exist(material):
    recommendations = generate_recommendations(material)

    required_fields = {
        "recommendation_type",
        "title",
        "description",
        "difficulty_level",
        "estimated_co2_saved"
    }

    for recommendation in recommendations:
        assert set(recommendation.keys()) == required_fields


# 6. Titles and descriptions must not be empty
@pytest.mark.parametrize("material", MATERIALS)
def test_recommendation_content_is_not_empty(material):
    recommendations = generate_recommendations(material)

    for recommendation in recommendations:
        assert recommendation["title"].strip()
        assert recommendation["description"].strip()


# 7. CO2 values must be None or non-negative numbers
@pytest.mark.parametrize("material", MATERIALS)
def test_co2_values_are_valid(material):
    recommendations = generate_recommendations(material)

    for recommendation in recommendations:
        co2 = recommendation["estimated_co2_saved"]

        assert co2 is None or (
            isinstance(co2, (int, float)) and co2 >= 0
        )


# 8. Material names should be case-insensitive
@pytest.mark.parametrize(
    "material",
    ["plastic", "Plastic", "PLASTIC", "PlAsTiC"]
)
def test_case_insensitive_material_lookup(material):
    recommendations = generate_recommendations(material)

    assert recommendations == RECOMMENDATION_RULES["PLASTIC"]


# 9. Leading and trailing spaces should be handled
def test_material_name_with_whitespace():
    recommendations = generate_recommendations("  GLASS  ")

    assert recommendations == RECOMMENDATION_RULES["GLASS"]


# 10. Unsupported material should raise ValueError
def test_unsupported_material():
    with pytest.raises(ValueError):
        generate_recommendations("WOOD")


# 11. Empty material name should raise ValueError
def test_empty_material_name():
    with pytest.raises(ValueError):
        generate_recommendations("")


# 12. Returned recommendations should not modify original rules
def test_returned_recommendations_are_independent():
    recommendations = generate_recommendations("PLASTIC")

    original_title = RECOMMENDATION_RULES["PLASTIC"][0]["title"]

    recommendations[0]["title"] = "Modified title"

    assert RECOMMENDATION_RULES["PLASTIC"][0]["title"] == original_title



# 13. None input should raise ValueError
def test_none_material_name():
    with pytest.raises(ValueError):
        generate_recommendations(None)


# 14. Numeric input should raise ValueError
@pytest.mark.parametrize("material", [123, 45.6])
def test_numeric_material_name(material):
    with pytest.raises(ValueError):
        generate_recommendations(material)


# 15. List input should raise ValueError
def test_list_material_name():
    with pytest.raises(ValueError):
        generate_recommendations(["PLASTIC"])


# 16. Dictionary input should raise ValueError
def test_dictionary_material_name():
    with pytest.raises(ValueError):
        generate_recommendations({"material": "PLASTIC"})


# 17. Whitespace-only input should raise ValueError
def test_whitespace_only_material_name():
    with pytest.raises(ValueError):
        generate_recommendations("     ")


# 18. Error message should identify invalid input
def test_invalid_input_error_message():
    with pytest.raises(
        ValueError,
        match="Material name must be a string"
    ):
        generate_recommendations(None)


def test_recommendations_do_not_claim_unverified_co2_savings():
    """CO2 estimates must remain unavailable until validated."""

    for material in MATERIALS:
        recommendations = generate_recommendations(material)

        for recommendation in recommendations:
            assert recommendation["estimated_co2_saved"] is None

            
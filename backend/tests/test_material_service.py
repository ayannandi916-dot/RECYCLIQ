from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.material_service import resolve_materials, resolve_materials_for_detections


def test_resolves_only_requested_materials_in_one_query():
    db = MagicMock()
    plastic = SimpleNamespace(name="Plastic")
    glass = SimpleNamespace(name="Glass")
    db.query.return_value.filter.return_value.all.return_value = [plastic, glass]

    result = resolve_materials(db, {"Plastic", "Glass"})

    assert result == {"Plastic": plastic, "Glass": glass}
    db.query.assert_called_once()
    db.query.return_value.filter.assert_called_once()


def test_empty_material_set_does_not_query_database():
    db = MagicMock()
    assert resolve_materials(db, set()) == {}
    db.query.assert_not_called()


def test_missing_database_material_raises_clear_error():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(name="Plastic")]

    with pytest.raises(RuntimeError, match="Missing materials in database: Glass"):
        resolve_materials(db, {"Plastic", "Glass"})


def test_resolves_distinct_materials_from_multiple_detections():
    db = MagicMock()
    plastic = SimpleNamespace(name="Plastic")
    glass = SimpleNamespace(name="Glass")
    db.query.return_value.filter.return_value.all.return_value = [plastic, glass]

    result = resolve_materials_for_detections(
        db,
        [
            {"material_name": "Plastic"},
            {"material_name": "Glass"},
            {"material_name": "Plastic"},
        ],
    )

    assert set(result) == {"Plastic", "Glass"}
    db.query.assert_called_once()

from app.models.user import User
from app.models.material import Material
from app.models.waste_scan import WasteScan
from app.models.scan_object import ScanObject
from app.models.scan_object_material import ScanObjectMaterial
from app.models.recommendation import Recommendation
from app.models.recycling_centre import RecyclingCentre
from app.models.recycling_centre_material import RecyclingCentreMaterial

__all__ = [
    "User",
    "Material",
    "WasteScan",
    "ScanObject",
    "ScanObjectMaterial",
    "Recommendation",
    "RecyclingCentre",
    "RecyclingCentreMaterial"
]
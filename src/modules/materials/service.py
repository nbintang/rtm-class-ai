from datetime import datetime, timezone
from uuid import uuid4

from src.core.exceptions import AppError
from src.modules.materials.processor import extract_text_from_content
from src.modules.materials.schemas import MaterialCreate, MaterialDetail, MaterialRead

_MATERIALS: dict[str, MaterialDetail] = {}


def _to_read_model(material: MaterialDetail) -> MaterialRead:
    return MaterialRead(
        id=material.id,
        title=material.title,
        owner_id=material.owner_id,
        source_type=material.source_type,
        text_preview=material.extracted_text[:160],
        created_at=material.created_at,
    )


def create_material(payload: MaterialCreate) -> MaterialDetail:
    extracted_text = extract_text_from_content(payload.content)
    material_id = str(uuid4())
    material = MaterialDetail(
        id=material_id,
        title=payload.title.strip(),
        owner_id=payload.owner_id,
        source_type="text",
        text_preview=extracted_text[:160],
        extracted_text=extracted_text,
        created_at=datetime.now(timezone.utc),
    )
    _MATERIALS[material_id] = material
    return material


def list_materials() -> list[MaterialRead]:
    return sorted((_to_read_model(item) for item in _MATERIALS.values()), key=lambda item: item.created_at, reverse=True)


def get_material(material_id: str) -> MaterialDetail:
    material = _MATERIALS.get(material_id)
    if material is None:
        raise AppError("Material not found", status_code=404, code="material_not_found")
    return material


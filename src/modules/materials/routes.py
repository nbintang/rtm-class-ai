from fastapi import APIRouter

from src.modules.materials import service
from src.modules.materials.schemas import MaterialCreate, MaterialDetail, MaterialRead

router = APIRouter(prefix="/materials", tags=["Materials"])


@router.post("/", response_model=MaterialDetail)
def create_material(payload: MaterialCreate) -> MaterialDetail:
    return service.create_material(payload)


@router.get("/", response_model=list[MaterialRead])
def list_materials() -> list[MaterialRead]:
    return service.list_materials()


@router.get("/{material_id}", response_model=MaterialDetail)
def get_material(material_id: str) -> MaterialDetail:
    return service.get_material(material_id)


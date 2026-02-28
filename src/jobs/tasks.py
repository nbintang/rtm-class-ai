from concurrent.futures import Future

from src.jobs.queue import queue_job
from src.modules.materials.schemas import MaterialCreate, MaterialDetail
from src.modules.materials.service import create_material


def process_material_task(title: str, content: str, owner_id: str | None = None) -> MaterialDetail:
    return create_material(MaterialCreate(title=title, content=content, owner_id=owner_id))


def enqueue_material_processing(title: str, content: str, owner_id: str | None = None) -> Future:
    return queue_job(process_material_task, title, content, owner_id)


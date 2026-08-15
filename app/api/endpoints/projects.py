"""Projects API — operator-owned project grouping for memory and chats.

Every route: authenticate → load project → verify project.owner_id ==
current_user.id → operate. Missing OR foreign projects are 404 (never
reveal existence). user_id is never accepted from the client.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import api_error, get_current_user
from app.core.database import get_sync_db
from app.models.memory import MemoryEntity
from app.models.user import User
from app.services import memory as mem

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None


class ProjectPatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None


def _project_payload(p) -> dict:
    return {
        "id": p.id,
        "owner_id": p.owner_id,
        "name": p.name,
        "description": p.description,
        "metadata": p.metadata_ or {},
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _require_owned_project(db, project_id: str, user: User):
    try:
        return mem.resolve_owned_project(db, project_id, user.id)
    except ValueError:
        raise api_error(404, "project_not_found", "Project not found")


@router.post("", status_code=201)
async def create_project_endpoint(
    request: ProjectCreateRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    from app.models.project import Project

    project = Project(owner_id=user.id, name=request.name.strip(), description=request.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_payload(project)


@router.get("")
async def list_projects_endpoint(
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    from app.models.project import Project
    from sqlalchemy import select

    projects = db.execute(
        select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.asc())
    ).scalars().all()
    return {"projects": [_project_payload(p) for p in projects], "total": len(projects)}


@router.patch("/{project_id}")
async def patch_project_endpoint(
    project_id: str,
    request: ProjectPatchRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    project = _require_owned_project(db, project_id, user)
    body = request.model_dump(exclude_unset=True)
    if "name" in body:
        project.name = body["name"].strip()
    if "description" in body:
        project.description = body["description"]
    db.commit()
    db.refresh(project)
    return _project_payload(project)


@router.delete("/{project_id}")
async def delete_project_endpoint(
    project_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    from sqlalchemy import func, select

    project = _require_owned_project(db, project_id, user)
    referencing = db.execute(
        select(func.count()).select_from(MemoryEntity).where(MemoryEntity.project_id == project_id)
    ).scalar_one()
    if referencing:
        raise api_error(409, "project_in_use", "Project still has memories; archive or delete them first")
    db.delete(project)
    db.commit()
    return {"status": "deleted"}
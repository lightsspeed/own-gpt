"""Memory V2 operator API — thin routes over app.services.memory.

Ownership: identity always comes from get_current_user; user_id is never
accepted from the client. Ownership is enforced in the service layer, so
foreign resources 404 indistinguishably from missing ones.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import api_error, get_current_user, get_embedding_provider
from app.core.database import get_sync_db
from app.models.memory import DOMAINS
from app.models.user import User
from app.services import memory as mem

router = APIRouter()

DomainName = Literal["semantic", "episodic", "preference", "procedural"]


class MemoryCreateRequest(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)
    domain: DomainName
    project_id: Optional[str] = None
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    expires_at: Optional[datetime] = None
    source_conversation_id: Optional[str] = None
    metadata: Optional[dict] = None


class MemoryPatchRequest(BaseModel):
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    expires_at: Optional[datetime] = None
    metadata: Optional[dict] = None
    # Declared so attempts to mutate content/status fail loudly (400) instead
    # of being silently dropped — statements are immutable in memory V2.
    statement: Optional[str] = None
    domain: Optional[str] = None
    status: Optional[str] = None


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    project_id: Optional[str] = None
    domains: Optional[list[DomainName]] = None
    k: int = Field(default=5, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)


class ActionRequest(BaseModel):
    note: str = ""


def _entity_payload(e) -> dict:
    return {
        "id": e.id,
        "user_id": e.user_id,
        "project_id": e.project_id,
        "domain": e.domain,
        "statement": e.statement,
        "source": e.source,
        "authority": e.authority,
        "confidence": e.confidence,
        "importance": e.importance,
        "source_conversation_id": e.source_conversation_id,
        "status": e.status,
        "version": e.version,
        "supersedes_id": e.supersedes_id,
        "conflicts_with_id": e.conflicts_with_id,
        "expires_at": e.expires_at,
        "last_accessed_at": e.last_accessed_at,
        "deleted_at": e.deleted_at,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
        "metadata": e.metadata_ or {},
    }


def _require_owned(db, memory_id: str, user: User):
    entity = mem.get_memory(db, memory_id, user.id)
    if entity is None:
        raise api_error(404, "memory_not_found", "Memory not found")
    return entity


@router.post("", status_code=201)
async def create_memory_endpoint(
    request: MemoryCreateRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
    provider=Depends(get_embedding_provider),
):
    try:
        body = request.model_dump(exclude_unset=True)
        entity = mem.create_memory(
            db,
            user_id=user.id,
            statement=body["statement"],
            domain=body["domain"],
            importance=body.get("importance", 0.5),
            project_id=body.get("project_id"),
            source_conversation_id=body.get("source_conversation_id"),
            metadata=body.get("metadata"),
            # expires_at only when the key was present (absent -> domain TTL).
            expires_at=body.get("expires_at"),
            apply_domain_ttl=True,
            embed=provider.embed if provider is not None else None,
        )
        return _entity_payload(entity)
    except mem.ProjectNotFoundError:
        raise api_error(404, "project_not_found", "Project not found")
    except ValueError as exc:
        raise api_error(400, "invalid_memory", str(exc))
    except HTTPException:
        raise


@router.get("")
async def list_memories_endpoint(
    project_id: Optional[str] = None,
    domain: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    entities = mem.list_memories(
        db,
        user.id,
        project_id=project_id,
        domain=domain,
        status=status,
        limit=min(max(limit, 1), 500),
        offset=max(offset, 0),
    )
    return {"memories": [_entity_payload(e) for e in entities], "total": len(entities)}


@router.get("/{memory_id}")
async def get_memory_endpoint(
    memory_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    entity = _require_owned(db, memory_id, user)
    return _entity_payload(entity)


@router.post("/search")
async def search_memories_endpoint(
    request: MemorySearchRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
    provider=Depends(get_embedding_provider),
):
    query = request.query.strip()
    if not query:
        raise api_error(400, "empty_query", "Query must not be empty")
    if provider is None:
        raise api_error(400, "embedding_provider_disabled", "Memory embeddings are disabled (provider 'none')")
    try:
        hits = mem.search_memories(
            db,
            user.id,
            query,
            project_id=request.project_id,
            domains=list(request.domains) if request.domains else None,
            k=request.k,
            min_score=request.min_score,
            max_tokens=request.max_tokens,
            embed=provider.embed,
        )
    except mem.ProjectNotFoundError:
        raise api_error(404, "project_not_found", "Project not found")
    except ValueError as exc:
        raise api_error(400, "invalid_search", str(exc))
    except HTTPException:
        raise
    return {
        "query": query,
        "hits": [
            {"id": h.entity.id, "statement": h.entity.statement, "domain": h.entity.domain, "score": h.score}
            for h in hits
        ],
    }


@router.patch("/{memory_id}")
async def patch_memory_endpoint(
    memory_id: str,
    request: MemoryPatchRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    _require_owned(db, memory_id, user)
    try:
        body = request.model_dump(exclude_unset=True)
        for immutable in ("statement", "domain", "status"):
            if immutable in body:
                raise api_error(400, "immutable_field", f"{immutable} cannot be changed; use supersede/transitions")
        entity = mem.update_memory_attributes(
            db,
            memory_id,
            user.id,
            importance=body.get("importance", mem._UNSET),
            expires_at=body.get("expires_at", mem._UNSET),
            metadata=body.get("metadata", mem._UNSET),
        )
        return _entity_payload(entity)
    except ValueError as exc:
        raise api_error(400, "invalid_update", str(exc))
    except HTTPException:
        raise


@router.post("/{memory_id}/promote")
async def promote_memory_endpoint(
    memory_id: str,
    request: ActionRequest = ActionRequest(),
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    _require_owned(db, memory_id, user)
    try:
        return _entity_payload(mem.promote_memory(db, memory_id, user.id, actor=user.id, note=request.note))
    except ValueError as exc:
        raise api_error(400, "invalid_transition", str(exc))
    except HTTPException:
        raise


@router.post("/{memory_id}/supersede")
async def supersede_memory_endpoint(
    memory_id: str,
    request: ActionRequest = ActionRequest(),
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    _require_owned(db, memory_id, user)
    try:
        return _entity_payload(mem.supersede_memory(db, memory_id, user.id, actor=user.id, note=request.note))
    except ValueError as exc:
        raise api_error(400, "invalid_transition", str(exc))
    except HTTPException:
        raise


@router.post("/{memory_id}/archive")
async def archive_memory_endpoint(
    memory_id: str,
    request: ActionRequest = ActionRequest(),
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    _require_owned(db, memory_id, user)
    try:
        return _entity_payload(mem.archive_memory(db, memory_id, user.id, actor=user.id, note=request.note))
    except ValueError as exc:
        raise api_error(400, "invalid_transition", str(exc))
    except HTTPException:
        raise


@router.post("/{memory_id}/restore")
async def restore_memory_endpoint(
    memory_id: str,
    request: ActionRequest = ActionRequest(),
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
    provider=Depends(get_embedding_provider),
):
    _require_owned(db, memory_id, user)
    try:
        entity = mem.restore_memory(
            db, memory_id, user.id, actor=user.id, note=request.note,
            embed=provider.embed if provider is not None else None,
        )
        return _entity_payload(entity)
    except mem.MemoryConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "conflict_refused",
                    "message": exc.message,
                    "candidate_ids": exc.candidate_ids,
                }
            },
        )
    except ValueError as exc:
        raise api_error(400, "invalid_transition", str(exc))
    except HTTPException:
        raise


@router.delete("/{memory_id}")
async def delete_memory_endpoint(
    memory_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_sync_db),
):
    _require_owned(db, memory_id, user)
    try:
        mem.delete_memory(db, memory_id, user.id, actor=user.id)
        return {"status": "deleted"}
    except ValueError as exc:
        raise api_error(400, "invalid_transition", str(exc))
    except HTTPException:
        raise
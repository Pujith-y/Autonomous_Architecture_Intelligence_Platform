"""
FastAPI wrapper around `build_repository_graph`.

Endpoints:
    POST /repositories/analyze   {"name": "...", "root_path": "/abs/path"}
        -> {"job_id": "..."}    kicks off a background scan + graph build

    GET  /repositories/{job_id}/status
        -> {"status": "pending" | "running" | "done" | "failed", "error": "..."}

    GET  /repositories/{job_id}/graph
        -> the RepositoryModel as JSON (entities, relationships, metadata)

This intentionally has no persistence layer (no DB, no Neo4j) -- results
live in memory for the process lifetime. Swap `_JOBS` for a real store
(Postgres row, Redis key, whatever) once you decide where the graph lands
downstream; the analysis logic itself doesn't change.

You still need to supply the file-discovery step (walking the repo into
DiscoveredFile/DiscoveredDirectory) -- `_discover_files` below is a minimal
stand-in using os.walk + a language-by-extension guess so this service runs
end-to-end; replace it with your actual discovery-stage implementation.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from graph_model import RepositoryModel, Entity, Relationship
from orchestrator import build_repository_graph, _EXTENSION_TO_EXTRACTOR

app = FastAPI(title="AAIP Repository Graph Service")


# ---------------------------------------------------------------------
# Minimal file discovery (replace with your real discovery-stage output)
# ---------------------------------------------------------------------

@dataclass
class _MinimalFile:
    path: Path
    relative_path: Path
    name: str
    extension: str
    is_binary: bool
    language: str | None = None


@dataclass
class _MinimalRepo:
    name: str
    files: list[_MinimalFile] = field(default_factory=list)


_IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "target"}


def _discover_files(name: str, root: Path) -> _MinimalRepo:
    files: list[_MinimalFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS and not d.startswith(".")]
        for fname in filenames:
            p = Path(dirpath) / fname
            if p.suffix.lower() not in _EXTENSION_TO_EXTRACTOR:
                continue
            files.append(
                _MinimalFile(
                    path=p,
                    relative_path=p.relative_to(root),
                    name=fname,
                    extension=p.suffix,
                    is_binary=False,
                )
            )
    return _MinimalRepo(name=name, files=files)


# ---------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------

@dataclass
class _Job:
    status: str = "pending"   # pending -> running -> done | failed
    error: str | None = None
    graph: RepositoryModel | None = None


_JOBS: dict[str, _Job] = {}


class AnalyzeRequest(BaseModel):
    name: str
    root_path: str


class AnalyzeResponse(BaseModel):
    job_id: str


class StatusResponse(BaseModel):
    status: str
    error: str | None = None


def _run_analysis(job_id: str, name: str, root_path: str) -> None:
    job = _JOBS[job_id]
    job.status = "running"
    try:
        legacy_repo = _discover_files(name, Path(root_path))
        job.graph = build_repository_graph(legacy_repo)
        job.status = "done"
    except Exception as exc:  # surface the failure rather than losing it silently
        job.status = "failed"
        job.error = str(exc)


@app.post("/repositories/analyze", response_model=AnalyzeResponse)
def analyze_repository(req: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    root = Path(req.root_path)
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {req.root_path}")

    job_id = uuid.uuid4().hex
    _JOBS[job_id] = _Job()
    background_tasks.add_task(_run_analysis, job_id, req.name, req.root_path)
    return AnalyzeResponse(job_id=job_id)


@app.get("/repositories/{job_id}/status", response_model=StatusResponse)
def get_status(job_id: str) -> StatusResponse:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return StatusResponse(status=job.status, error=job.error)


def _entity_to_dict(e: Entity) -> dict[str, Any]:
    return {
        "id": e.id,
        "kind": e.kind.value,
        "name": e.name,
        "qualified_name": e.qualified_name,
        "language": e.language,
        "location": (
            {
                "file": str(e.location.file),
                "start_line": e.location.start_line,
                "end_line": e.location.end_line,
                "start_column": e.location.start_column,
                "end_column": e.location.end_column,
            }
            if e.location
            else None
        ),
        "parameters": [
            {
                "name": p.name,
                "type": p.type.name if p.type else None,
                "default_value": p.default_value,
                "is_variadic": p.is_variadic,
                "is_keyword_only": p.is_keyword_only,
            }
            for p in e.parameters
        ],
        "return_type": e.return_type.name if e.return_type else None,
        "metadata": e.metadata,
    }


def _relationship_to_dict(r: Relationship) -> dict[str, Any]:
    return {"source_id": r.source_id, "target_id": r.target_id, "kind": r.kind.value, "metadata": r.metadata}


@app.get("/repositories/{job_id}/graph")
def get_graph(job_id: str) -> dict[str, Any]:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    if job.status != "done":
        raise HTTPException(status_code=409, detail=f"Job is not finished (status: {job.status})")
    graph = job.graph
    assert graph is not None
    return {
        "name": graph.name,
        "entities": [_entity_to_dict(e) for e in graph.entities],
        "relationships": [_relationship_to_dict(r) for r in graph.relationships],
        "metadata": graph.metadata,
    }

"""FastAPI backend for the Synth Head config editor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import manifests as mf
from . import profiles as prof
from .chaos_schema import chaos_joints_schema
from .schema import CONFIG_FILES

app = FastAPI(title="Synth Head Config", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    source: str | None = None


class ProfileRename(BaseModel):
    new_name: str = Field(min_length=1, max_length=64)


class ConfigWrite(BaseModel):
    data: dict[str, Any]


class ManifestRegister(BaseModel):
    ids: list[str] = Field(min_length=1)
    note: str = ""


@app.on_event("startup")
def _startup() -> None:
    prof.ensure_profiles_layout()
    mf.ensure_manifests()


@app.get("/api/schema/chaos_joints")
def get_chaos_joints_schema() -> dict:
    return chaos_joints_schema()


@app.get("/api/schema")
def get_schema() -> dict:
    return {"files": CONFIG_FILES}


@app.get("/api/profiles")
def get_profiles() -> dict:
    return {
        "active": prof.get_active_profile(),
        "profiles": prof.list_profiles(),
    }


@app.post("/api/profiles")
def create_profile(body: ProfileCreate) -> dict:
    try:
        prof.create_profile(body.name, body.source)
    except prof.ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "name": body.name}


@app.post("/api/profiles/{name}/activate")
def activate_profile(name: str) -> dict:
    try:
        prof.activate_profile(name)
    except prof.ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "active": name}


@app.delete("/api/profiles/{name}")
def delete_profile(name: str) -> dict:
    try:
        prof.delete_profile(name)
    except prof.ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/profiles/{name}/rename")
def rename_profile(name: str, body: ProfileRename) -> dict:
    try:
        prof.rename_profile(name, body.new_name)
    except prof.ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "name": body.new_name}


@app.get("/api/profiles/{name}/validate")
def validate_profile(name: str) -> dict:
    try:
        return prof.validate_profile(name)
    except prof.ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/profiles/{name}/config/{file_id}")
def read_config(name: str, file_id: str) -> dict:
    try:
        return prof.read_config_file(name, file_id)
    except prof.ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON on disk: {exc}") from exc


@app.put("/api/profiles/{name}/config/{file_id}")
def write_config(name: str, file_id: str, body: ConfigWrite) -> dict:
    try:
        prof.write_config_file(name, file_id, body.data)
        mf.ingest_config_file(file_id, body.data)
    except prof.ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/api/manifests")
def get_manifests() -> dict:
    return {"manifests": mf.list_manifests()}


@app.get("/api/manifests/{manifest_id}")
def get_manifest(manifest_id: str) -> dict:
    try:
        return mf.get_manifest(manifest_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/manifests/{manifest_id}/register")
def register_manifest_items(manifest_id: str, body: ManifestRegister) -> dict:
    try:
        return mf.register_items(manifest_id, body.ids, note=body.note)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/profiles/{name}/registry")
def get_registry(name: str) -> dict:
    try:
        return mf.build_registry(name)
    except prof.ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


_web_static = Path(__file__).resolve().parent.parent / "web" / "static"
if _web_static.is_dir():
    app.mount("/assets", StaticFiles(directory=_web_static / "assets"), name="assets")

    @app.get("/")
    def _index():
        from fastapi.responses import FileResponse

        return FileResponse(_web_static / "index.html")

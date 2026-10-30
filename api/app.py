"""FastAPI application — Systematic Review Processor UI."""

from __future__ import annotations

import io
import os
import zipfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sr_processor.config import DEFAULT_MODEL, SUPPORTED_MODELS
from sr_processor.prompt import FRAMEWORK_BRIEFING_FILENAME

from api.job_runner import JobRunner
from api.workspace import MAX_PAPERS, Workspace

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

workspace = Workspace(ROOT)
workspace.ensure_dirs()
runner = JobRunner(workspace)

app = FastAPI(title="Systematic Review Processor", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    workers: int = Field(default=1, ge=1, le=2)
    model: str = Field(default=DEFAULT_MODEL)


class ApiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=10)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "max_papers": MAX_PAPERS,
        "default_model": DEFAULT_MODEL,
        "supported_models": [
            {"id": model_id, "label": label} for model_id, label in SUPPORTED_MODELS
        ],
        **runner.api_key_info(),
    }


@app.post("/api/api-key")
def set_api_key(body: ApiKeyRequest):
    try:
        runner.set_api_key(body.api_key)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, **runner.api_key_info()}


@app.delete("/api/api-key")
def clear_api_key():
    runner.clear_api_key()
    return {"ok": True, **runner.api_key_info()}


@app.get("/api/status")
def status():
    return runner.get_status()


@app.get("/api/events")
async def events():
    """Server-Sent Events for live job updates."""
    import asyncio
    import json

    queue: asyncio.Queue[dict] = asyncio.Queue()

    def on_update(payload: dict) -> None:
        try:
            queue.put_nowait(payload)
        except Exception:
            pass

    runner.subscribe(on_update)
    loop = asyncio.get_event_loop()

    async def stream():
        yield f"data: {json.dumps(runner.get_status())}\n\n"
        while True:
            try:
                payload = await loop.run_in_executor(None, queue.get, True, 1.0)
                yield f"data: {json.dumps(payload)}\n\n"
                if payload.get("job", {}).get("state") in (
                    "completed",
                    "cancelled",
                    "failed",
                    "idle",
                ):
                    if payload.get("job", {}).get("state") != "running":
                        await asyncio.sleep(0.5)
                        yield f"data: {json.dumps(runner.get_status())}\n\n"
                        break
            except Exception:
                yield f"data: {json.dumps(runner.get_status())}\n\n"
                await asyncio.sleep(2)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/prompt")
async def upload_prompt(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "Prompt must be a .docx file")
    content = await file.read()
    workspace.prompt_path.write_bytes(content)
    workspace.set_prompt_display_name(file.filename)
    return {"ok": True, "name": workspace.display_prompt_name()}


@app.delete("/api/prompt")
def remove_prompt():
    if runner.is_running():
        raise HTTPException(409, "Stop the job before removing the prompt")
    workspace.clear_prompt()
    return {"ok": True}


@app.post("/api/framework")
async def upload_framework(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Framework file must be a PDF")
    content = await file.read()
    if not content:
        raise HTTPException(400, "Framework PDF is empty")
    workspace.framework_path.write_bytes(content)
    workspace.set_framework_display_name(file.filename)
    return {"ok": True, "name": workspace.display_framework_name()}


@app.delete("/api/framework")
def remove_framework():
    if runner.is_running():
        raise HTTPException(409, "Stop the job before removing the framework PDF")
    workspace.clear_framework()
    return {"ok": True}


@app.post("/api/pdfs")
async def upload_pdfs(files: list[UploadFile] = File(...)):
    workspace.ensure_dirs()
    existing = len(workspace.list_pdfs())
    added = 0
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            continue
        if existing + added >= MAX_PAPERS:
            raise HTTPException(400, f"Maximum {MAX_PAPERS} PDFs allowed")
        dest = workspace.papers_dir / Path(f.filename).name
        dest.write_bytes(await f.read())
        added += 1
    return {"ok": True, "added": added, "total": len(workspace.list_pdfs())}


@app.delete("/api/pdfs/{filename}")
def delete_pdf(filename: str):
    path = workspace.papers_dir / filename
    if not path.exists():
        raise HTTPException(404, "PDF not found")
    path.unlink()
    out = workspace.output_dir / f"{path.stem}.json"
    err = workspace.output_dir / f"{path.stem}_ERROR.json"
    out.unlink(missing_ok=True)
    err.unlink(missing_ok=True)
    return {"ok": True}


@app.post("/api/clear-outputs")
def clear_outputs():
    if runner.is_running():
        raise HTTPException(409, "Stop the job before clearing outputs")
    for f in workspace.output_dir.glob("*"):
        if f.is_file():
            f.unlink()
    return {"ok": True}


@app.post("/api/reset")
def reset_workspace():
    """Clear all uploaded papers AND all results — a clean slate for a new run.

    Keeps the coding prompt, optional framework PDF, and API key so the user only needs to re-add papers.
    """
    if runner.is_running():
        raise HTTPException(409, "Stop the job before clearing everything")
    removed_pdfs = 0
    for pdf in workspace.papers_dir.glob("*.pdf"):
        pdf.unlink(missing_ok=True)
        removed_pdfs += 1
    for f in workspace.output_dir.glob("*"):
        if f.is_file():
            f.unlink()
    return {"ok": True, "removed_pdfs": removed_pdfs}


@app.post("/api/run")
def run_job(body: RunRequest):
    try:
        runner.start(workers=body.workers, model=body.model)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return runner.get_status()


@app.post("/api/stop")
def stop_job():
    runner.stop()
    return runner.get_status()


NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


def _stamped(stem: str, ext: str) -> str:
    return f"{stem}_{datetime.now():%Y%m%d_%H%M%S}.{ext}"


@app.get("/api/download/csv")
def download_csv():
    path = workspace.output_dir / "systematic_review_results.csv"
    if not path.exists():
        raise HTTPException(404, "CSV not ready. Finish processing first")
    return FileResponse(
        path,
        filename=_stamped("systematic_review_results", "csv"),
        media_type="text/csv",
        headers=NO_STORE,
    )


@app.get("/api/download/framework-briefing")
def download_framework_briefing():
    path = workspace.output_dir / FRAMEWORK_BRIEFING_FILENAME
    if not path.exists():
        raise HTTPException(404, "No framework briefing yet. Run with a framework PDF attached")
    return FileResponse(
        path,
        filename=_stamped("framework_briefing", "txt"),
        media_type="text/plain",
        headers=NO_STORE,
    )


@app.get("/api/download/change-log")
def download_change_log():
    from sr_processor.change_log import write_change_log

    path = write_change_log(workspace.output_dir)
    return FileResponse(
        path,
        filename=_stamped("change_log", "csv"),
        media_type="text/csv",
        headers=NO_STORE,
    )


@app.get("/api/download/zip")
def download_zip():
    json_files = [
        f
        for f in workspace.output_dir.glob("*.json")
        if not f.name.endswith("_ERROR.json")
        and f.name != "batch_summary.json"
    ]
    if not json_files:
        raise HTTPException(404, "No results to download")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for jf in json_files:
            zf.write(jf, jf.name)
        csv = workspace.output_dir / "systematic_review_results.csv"
        if csv.exists():
            zf.write(csv, csv.name)
        change_log = workspace.output_dir / "change_log.csv"
        if change_log.exists():
            zf.write(change_log, change_log.name)
        briefing = workspace.output_dir / FRAMEWORK_BRIEFING_FILENAME
        if briefing.exists():
            zf.write(briefing, briefing.name)
        log = workspace.output_dir / "processor.log"
        if log.exists():
            zf.write(log, log.name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={_stamped('review_results', 'zip')}",
            **NO_STORE,
        },
    )


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

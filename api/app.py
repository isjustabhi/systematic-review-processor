"""FastAPI application — Systematic Review Processor UI."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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


class ApiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=10)


@app.get("/api/health")
def health():
    return {"ok": True, "max_papers": MAX_PAPERS, **runner.api_key_info()}


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
    return {"ok": True, "name": workspace.prompt_path.name}


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


@app.post("/api/run")
def run_job(body: RunRequest):
    try:
        runner.start(workers=body.workers)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return runner.get_status()


@app.post("/api/stop")
def stop_job():
    runner.stop()
    return runner.get_status()


@app.get("/api/download/csv")
def download_csv():
    path = workspace.output_dir / "systematic_review_results.csv"
    if not path.exists():
        raise HTTPException(404, "CSV not ready — finish processing first")
    return FileResponse(path, filename=path.name, media_type="text/csv")


@app.get("/api/download/change-log")
def download_change_log():
    from sr_processor.change_log import write_change_log

    path = write_change_log(workspace.output_dir)
    return FileResponse(path, filename=path.name, media_type="text/csv")


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
        log = workspace.output_dir / "processor.log"
        if log.exists():
            zf.write(log, log.name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=review_results.zip"},
    )


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from apps.api import service
from apps.api.service import (
    EvaluateRunRequest,
    ExtractEvalStandardsRequest,
    GenerateAssetsRequest,
    RunEvaluationRequest,
    SyncPromptsRequest,
)
from dialogue_simulator.tracing import setup_tracing, shutdown_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing("dialogue-eval-api")
    try:
        yield
    finally:
        shutdown_tracing()


app = FastAPI(
    title="DialogueEval API",
    description="API wrapper for asset generation, dialogue simulation, and evaluation reports.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return service.health()


@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        return service.save_uploaded_file(file.filename or "upload", content)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/eval-standards/extract")
def extract_eval_standards(request: ExtractEvalStandardsRequest):
    try:
        return service.extract_eval_standards(request)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/prompts/status")
def get_prompt_status():
    try:
        return service.get_prompt_status()
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/prompts/sync")
def sync_prompts(request: SyncPromptsRequest):
    try:
        return service.sync_prompts(request)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/assets")
def list_assets(include_legacy: bool = False):
    try:
        return {"assets": service.list_assets(include_legacy=include_legacy)}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/assets/{scene_id}")
def get_asset(scene_id: str):
    try:
        return service.summarize_asset_dir(service.PROJECT_ROOT / "outputs/assets" / scene_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/assets/{scene_id}/files/{filename}", response_class=PlainTextResponse)
def get_asset_file(scene_id: str, filename: str):
    try:
        return service.read_asset_file(scene_id, filename)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/assets/generate")
def generate_assets(request: GenerateAssetsRequest):
    try:
        return service.generate_assets(request)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/runs")
def list_runs():
    try:
        return {"runs": service.list_runs()}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    try:
        return service.summarize_run_dir(service.PROJECT_ROOT / "outputs/runs" / run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/runs")
def run_evaluation(request: RunEvaluationRequest):
    try:
        return service.run_evaluation(request)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/runs/evaluate")
def evaluate_existing_run(request: EvaluateRunRequest):
    try:
        return service.evaluate_existing_run(request)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/runs/{run_id}/reports/{filename}", response_class=PlainTextResponse)
def get_run_report(run_id: str, filename: str):
    try:
        return service.read_run_report(run_id, filename)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/runs/{run_id}/case_reports")
def list_case_reports(run_id: str):
    try:
        run_dir = service.PROJECT_ROOT / "outputs/runs" / run_id
        return {"case_reports": service.list_case_reports(run_dir)}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/runs/{run_id}/case_reports/{case_id}", response_class=PlainTextResponse)
def get_case_report(run_id: str, case_id: str):
    try:
        return service.read_case_report(run_id, case_id)
    except Exception as exc:
        raise _http_error(exc) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))

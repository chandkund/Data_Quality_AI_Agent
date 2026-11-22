"""HTTP API for uploading datasets and running the quality agent."""

import io
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from agent import run_agent


load_dotenv(Path(__file__).with_name(".env"))

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 50_000
SAMPLE_FILE = Path(__file__).parent / "data" / "dirty.csv"

# Origins are configured as a comma-separated list in .env.
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Data Quality AI Agent API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _run_report(dataframe):
    """Run the agent and add dataset metadata without removing report fields."""
    report = await run_in_threadpool(run_agent, dataframe)
    if not isinstance(report, dict):
        report = {"score": 0, "issues": [], "tools_used": [], "error": "Invalid agent response."}

    report = dict(report)
    report.setdefault("rows", int(len(dataframe)))
    report.setdefault("columns", int(len(dataframe.columns)))
    if not isinstance(report.get("summary"), str) or not report["summary"].strip():
        if report.get("error"):
            report["summary"] = "The analysis could not be completed because an AI provider failed."
        else:
            report["summary"] = "The analysis completed; no summary was returned by the model."
    return report


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/analyze")
@limiter.limit("5/minute")
async def analyze(request: Request, file: UploadFile = File(...)):
    """Read an uploaded CSV into memory and return its data quality report."""
    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    media_type = (file.content_type or "").split(";", 1)[0].lower()
    accepted_types = {
        "",
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "text/plain",
        "application/octet-stream",
    }
    if media_type not in accepted_types:
        raise HTTPException(status_code=400, detail="The uploaded file must be a CSV.")

    try:
        # Read only one byte past the limit so oversized uploads can be rejected.
        file_bytes = await file.read(MAX_FILE_SIZE + 1)
        if not file_bytes:
            raise HTTPException(status_code=400, detail="The uploaded CSV is empty.")
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="The CSV exceeds the 5 MB file size limit.")

        # pandas reads from a byte stream; the uploaded file is not written by the application.
        dataframe = pd.read_csv(io.BytesIO(file_bytes))
        if dataframe.empty:
            raise HTTPException(status_code=400, detail="The CSV contains no data rows.")
        if len(dataframe) > MAX_ROWS:
            raise HTTPException(
                status_code=400,
                detail=f"The CSV exceeds the {MAX_ROWS:,} row limit.",
            )
    except HTTPException:
        raise
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {error}") from error
    finally:
        await file.close()

    return await _run_report(dataframe)


@app.get("/sample")
@limiter.limit("5/minute")
async def analyze_sample(request: Request):
    """Run the agent on the bundled dirty sample dataset."""
    try:
        dataframe = pd.read_csv(SAMPLE_FILE, keep_default_na=False, na_values=[""])
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise HTTPException(status_code=500, detail=f"Could not read sample dataset: {error}") from error

    return await _run_report(dataframe)

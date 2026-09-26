import os
import re
import uuid
import asyncio
from pathlib import Path
from typing import Optional

import yt_dlp
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("DOWNLOADER_API_KEY", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
MAX_DURATION_SECONDS = int(os.getenv("MAX_DURATION_SECONDS", "3600"))

app = FastAPI(
    title="YouTube Downloader GPT Action",
    version="1.0.0",
    description="Downloads videos only when the requester is authorized to do so.",
)

app.mount("/files", StaticFiles(directory=str(DOWNLOAD_DIR)), name="files")


class InfoRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL")


class DownloadRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL")
    format: str = Field(default="mp4", pattern="^(mp4|mp3)$")


def check_auth(x_api_key: Optional[str]):
    if not API_KEY:
        raise HTTPException(500, "Server API key is not configured.")
    if x_api_key != API_KEY:
        raise HTTPException(401, "Invalid API key.")


def validate_youtube_url(url: str) -> str:
    pattern = re.compile(
        r"^https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]{11}"
        r"|youtu\.be/[\w-]{11}"
        r"|youtube\.com/shorts/[\w-]{11})(?:[&?][^\s]*)?$",
        re.I,
    )
    if not pattern.match(url.strip()):
        raise HTTPException(400, "Please provide a valid YouTube video URL.")
    return url.strip()


def get_info(url: str):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    duration = info.get("duration") or 0
    if duration > MAX_DURATION_SECONDS:
        raise HTTPException(
            400,
            f"Video is longer than the server limit of {MAX_DURATION_SECONDS} seconds.",
        )
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "duration_seconds": duration,
        "channel": info.get("channel"),
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url"),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/info")
async def video_info(req: InfoRequest, x_api_key: Optional[str] = Header(None)):
    check_auth(x_api_key)
    url = validate_youtube_url(req.url)
    return get_info(url)


@app.post("/download")
async def download(req: DownloadRequest, x_api_key: Optional[str] = Header(None)):
    check_auth(x_api_key)
    url = validate_youtube_url(req.url)

    # Inspect metadata first and enforce duration limits.
    info = get_info(url)
    job_id = uuid.uuid4().hex
    output_template = str(DOWNLOAD_DIR / f"{job_id}.%(ext)s")

    if req.format == "mp3":
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
    else:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        raise HTTPException(500, f"Download failed: {str(exc)[:300]}")

    matches = list(DOWNLOAD_DIR.glob(f"{job_id}.*"))
    matches = [p for p in matches if p.is_file()]
    if not matches:
        raise HTTPException(500, "Download completed but output file was not found.")

    output = matches[0]
    filename = f"{info['title'] or 'video'}{output.suffix}"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("_") or output.name

    public_url = f"{PUBLIC_BASE_URL}/files/{output.name}" if PUBLIC_BASE_URL else None

    return {
        "status": "ready",
        "title": info["title"],
        "format": req.format,
        "filename": safe_name,
        "download_url": public_url,
        "path": f"/files/{output.name}",
        "note": "Use this only for content you are authorized to download.",
    }


@app.get("/files/{filename}")
async def serve_file(filename: str):
    # StaticFiles handles the actual path safely; this endpoint is kept out of
    # the Action schema and is intended for browser/file retrieval.
    file_path = DOWNLOAD_DIR / Path(filename).name
    if not file_path.exists():
        raise HTTPException(404, "File not found.")
    return FileResponse(file_path, filename=file_path.name)

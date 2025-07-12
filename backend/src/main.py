import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

backend_dir = Path(__file__).parent.parent.resolve()
transferwee_dir = backend_dir / "transferwee"

app = FastAPI()

DOWNLOADS_DIR = backend_dir / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)
DOWNLOAD_LOG_FILE = backend_dir / "download.log.json"
log_lock = threading.Lock()


class DownloadRequest(BaseModel):
    url: str


@app.get("/")
def read_root():
    return {"message": "Backend for wetransfer-grab is running."}


@app.post("/download")
def download_url(request: DownloadRequest):
    """
    Downloads files from a WeTransfer URL using the transferwee script
    and logs the download. Prevents re-downloading of the same URL.
    """
    with log_lock:
        # Load existing log
        if DOWNLOAD_LOG_FILE.exists():
            with open(DOWNLOAD_LOG_FILE, "r") as f:
                try:
                    log_entries = json.load(f)
                except json.JSONDecodeError:
                    log_entries = []
        else:
            log_entries = []

        # Check if URL has already been downloaded
        for entry in log_entries:
            if entry.get("url") == request.url:
                return {
                    "message": "URL already downloaded",
                    "url": request.url,
                    "files": entry.get("files"),
                }

        files_before = set(os.listdir(DOWNLOADS_DIR))

        try:
            transferwee_script_path = transferwee_dir / "transferwee.py"
            python_executable = sys.executable

            result = subprocess.run(
                [
                    python_executable,
                    str(transferwee_script_path),
                    "download",
                    request.url,
                ],
                cwd=DOWNLOADS_DIR,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                error_message = f"Download failed: {result.stderr or result.stdout}"
                raise HTTPException(status_code=500, detail=error_message)

            files_after = set(os.listdir(DOWNLOADS_DIR))
            new_files = sorted(list(files_after - files_before))

            if new_files:
                log_entries.append(
                    {
                        "url": request.url,
                        "files": new_files,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                with open(DOWNLOAD_LOG_FILE, "w") as f:
                    json.dump(log_entries, f, indent=2)

            return {
                "message": f"Download completed for {request.url}",
                "downloaded_files": new_files,
                "output": result.stdout,
            }
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=500, detail=f"An unexpected error occurred: {e}"
            )

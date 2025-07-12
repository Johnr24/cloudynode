import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

backend_dir = Path(__file__).parent.parent.resolve()
transferwee_dir = backend_dir / "transferwee"

app = FastAPI()

DOWNLOADS_DIR = backend_dir / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)


class DownloadRequest(BaseModel):
    url: str


@app.get("/")
def read_root():
    return {"message": "Backend for wetransfer-grab is running."}


@app.post("/download")
def download_url(request: DownloadRequest):
    """
    Downloads files from a WeTransfer URL using the transferwee script.
    """
    try:
        transferwee_script_path = transferwee_dir / "transferwee.py"
        python_executable = sys.executable

        result = subprocess.run(
            [python_executable, str(transferwee_script_path), "download", request.url],
            cwd=DOWNLOADS_DIR,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            error_message = f"Download failed: {result.stderr or result.stdout}"
            raise HTTPException(status_code=500, detail=error_message)

        return {"message": f"Download completed for {request.url}", "output": result.stdout}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

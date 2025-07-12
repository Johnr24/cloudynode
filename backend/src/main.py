import os
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add transferwee to path to allow imports
# This is a bit of a hack, but it's the easiest way to use the script
# as a library without modifying it.
backend_dir = Path(__file__).parent.parent.resolve()
transferwee_dir = backend_dir / "transferwee"
sys.path.insert(0, str(transferwee_dir))

from transferwee import download as transferwee_download

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
    Downloads files from a WeTransfer URL.
    """
    # transferwee's download function expects an argparse-like object.
    args = SimpleNamespace(
        url=[request.url],
        output=None,
        verbose=False,
        g=False,  # do not just print the link
    )

    current_dir = os.getcwd()
    try:
        os.chdir(DOWNLOADS_DIR)
        transferwee_download(args)
        return {"message": f"Download started for {request.url}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.chdir(current_dir)

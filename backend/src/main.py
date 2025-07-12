import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import BaseModel, EmailStr

backend_dir = Path(__file__).parent.parent.resolve()
load_dotenv(dotenv_path=backend_dir.parent / ".env")
transferwee_dir = backend_dir / "transferwee"

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOADS_DIR = backend_dir / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)
DOWNLOAD_LOG_FILE = backend_dir / "download.log.json"
GRAPH_STATE_FILE = backend_dir / "graph.json"
log_lock = threading.Lock()
graph_lock = threading.Lock()


class Node(BaseModel):
    id: str
    type: str | None = None
    position: Dict[str, float]
    data: Dict[str, Any]
    className: str | None = None
    width: int | None = None
    height: int | None = None
    selected: bool | None = None
    positionAbsolute: Dict[str, float] | None = None
    dragging: bool | None = None


class Edge(BaseModel):
    id: str
    source: str
    target: str
    type: str | None = None
    animated: bool | None = None


class GraphState(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


class DownloadRequest(BaseModel):
    url: str


class EmailSchema(BaseModel):
    recipients: list[EmailStr]
    subject: str
    body: str


@app.get("/")
def read_root():
    return {"message": "Backend for wetransfer-grab is running."}


@app.get("/graph", response_model=GraphState)
def get_graph():
    """
    Retrieves the graph state from a JSON file.
    """
    with graph_lock:
        if not GRAPH_STATE_FILE.exists():
            return {"nodes": [], "edges": []}
        with open(GRAPH_STATE_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"nodes": [], "edges": []}


@app.post("/graph")
def save_graph(graph_state: GraphState):
    """
    Saves the graph state to a JSON file.
    """
    with graph_lock:
        with open(GRAPH_STATE_FILE, "w") as f:
            json.dump(graph_state.dict(), f, indent=2)
    return {"message": "Graph state saved"}


@app.post("/email/send")
async def send_email(email: EmailSchema) -> dict:
    """
    Sends an email to a list of recipients.
    """
    message = MessageSchema(
        subject=email.subject,
        recipients=email.recipients,
        body=email.body,
        subtype=MessageType.html,
    )

    fm = FastMail(conf)
    await fm.send_message(message)
    return {"message": "Email has been sent"}


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

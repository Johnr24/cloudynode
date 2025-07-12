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
from pydantic import BaseModel, EmailStr
import re
from jmapc import Client
from jmapc.methods.email import Get as EmailGet, Query as EmailQuery, Set as EmailSet
from jmapc.methods.email_submission import Set as EmailSubmissionSet
from jmapc.methods.mailbox import Query as MailboxQuery

backend_dir = Path(__file__).parent.parent.resolve()
load_dotenv(dotenv_path=backend_dir.parent / ".env")
transferwee_dir = backend_dir / "transferwee"

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
    Sends an email using Fastmail JMAP API.
    """
    username = os.getenv("FASTMAIL_USERNAME")
    token = os.getenv("FASTMAIL_API_TOKEN")

    if not username or not token:
        raise HTTPException(
            status_code=500,
            detail="FASTMAIL_USERNAME and FASTMAIL_API_TOKEN must be set in .env file",
        )

    try:
        async with Client(
            host="api.fastmail.com", bearer_token=token
        ) as client:
            account_id = client.get_account_id()
            identities = await client.get_identities()
            if not identities:
                raise HTTPException(status_code=500, detail="No identities found for Fastmail account")
            identity_id = identities[0].id

            email_submission_set = EmailSubmissionSet(account_id=account_id)
            email_submission_set.create(
                identity_id=identity_id,
                email={
                    "to": [{"email": recipient} for recipient in email.recipients],
                    "subject": email.subject,
                    "bodyValues": {
                        "1": {"value": email.body, "isEncodingProblem": False, "isTruncated": False}
                    },
                    "bodyStructure": {"partId": "1", "type": "text/plain"},
                },
            )
            await client.process(email_submission_set)

        return {"message": "Email has been sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")


@app.post("/scan-emails")
async def scan_emails():
    """
    Scans unread emails for WeTransfer links and marks them as read.
    """
    username = os.getenv("FASTMAIL_USERNAME")
    token = os.getenv("FASTMAIL_API_TOKEN")

    if not username or not token:
        raise HTTPException(
            status_code=500,
            detail="FASTMAIL_USERNAME and FASTMAIL_API_TOKEN must be set in .env file",
        )

    found_urls = []
    try:
        async with Client(
            host="api.fastmail.com", bearer_token=token
        ) as client:
            account_id = client.get_account_id()

            # Find the inbox mailbox ID
            mailbox_query = MailboxQuery(account_id=account_id)
            mailbox_query.filter(role="inbox")
            mailbox_query.limit(1)
            response = await client.process(mailbox_query)
            inbox_id = response.get_method_responses()[0].ids[0]

            # Query for unread emails in the inbox
            email_query = EmailQuery(account_id=account_id)
            email_query.filter(in_mailbox=inbox_id, is_unread=True)
            response = await client.process(email_query)
            unread_email_ids = response.get_method_responses()[0].ids

            if not unread_email_ids:
                return {"message": "No unread emails found.", "urls": []}

            # Fetch email bodies
            email_get = EmailGet(account_id=account_id)
            email_get.ids(unread_email_ids)
            email_get.properties(["bodyHtml", "bodyPlain"])
            response = await client.process(email_get)
            emails = response.get_method_responses()[0].list

            # Search for WeTransfer links
            url_pattern = re.compile(r"https?://we\.tl/[a-zA-Z0-9\-\_]+")
            for email in emails:
                body = email.body_html or email.body_plain or ""
                urls = url_pattern.findall(body)
                found_urls.extend(urls)

            # Mark emails as read
            if unread_email_ids:
                email_set = EmailSet(account_id=account_id)
                email_set.update(ids=unread_email_ids, patch={"isUnread": False})
                await client.process(email_set)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan emails: {e}")

    return {
        "message": f"Found {len(set(found_urls))} new WeTransfer links.",
        "urls": list(set(found_urls)),
    }


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

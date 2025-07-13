import json
import os
import shutil
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
import httpx
from bs4 import BeautifulSoup

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
EMAIL_SCAN_LOG_FILE = backend_dir / "email_scan.log.json"
GRAPH_STATE_FILE = backend_dir / "graph.json"
CONFIG_FILE = backend_dir / "config.json"
log_lock = threading.Lock()
graph_lock = threading.Lock()
config_lock = threading.Lock()


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


class Config(BaseModel):
    sender_emails: List[str] = []
    download_directory: str | None = None


class EmailSchema(BaseModel):
    recipients: list[EmailStr]
    subject: str
    body: str


def get_config() -> Config:
    with config_lock:
        if not CONFIG_FILE.exists():
            return Config()
        with open(CONFIG_FILE, "r") as f:
            try:
                return Config(**json.load(f))
            except (json.JSONDecodeError, TypeError):
                return Config()


def save_config(config: Config):
    with config_lock:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config.dict(), f, indent=2)


@app.get("/config", response_model=Config)
def get_config_endpoint():
    """
    Retrieves the application configuration.
    """
    return get_config()


@app.post("/config")
def save_config_endpoint(config: Config):
    """
    Saves the application configuration.
    """
    save_config(config)
    return {"message": "Configuration saved"}


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




async def _call_jmap(client: httpx.AsyncClient, api_url: str, using: list, calls: list):
    response = await client.post(api_url, json={"using": using, "methodCalls": calls})
    response.raise_for_status()
    data = response.json()
    if "methodResponses" not in data:
        raise Exception(f"Invalid JMAP response: {data}")
    for res in data["methodResponses"]:
        if res[0] == "error":
            raise Exception(f"JMAP error: {res[1]}")
    return data["methodResponses"]


def _find_text_parts(
    body_structure: dict[str, Any] | None,
) -> List[Dict[str, str]]:
    """
    Recursively find text/plain or text/html parts from a JMAP bodyStructure.
    Returns a list of dicts with 'partId' and 'type'.
    """
    parts = []

    def recurse(part):
        part_type = part.get("type")
        if part_type in ("text/plain", "text/html") and "partId" in part:
            parts.append({"partId": part["partId"], "type": part_type})
        if "subParts" in part:
            for sub_part in part["subParts"]:
                recurse(sub_part)

    if body_structure:
        recurse(body_structure)
    return parts


@app.post("/email/send")
async def send_email(email: EmailSchema) -> dict:
    """
    Sends an email using Fastmail JMAP API.
    """
    token = os.getenv("FASTMAIL_API_TOKEN")
    if token:
        token = token.strip()

    if not token:
        raise HTTPException(
            status_code=500, detail="FASTMAIL_API_TOKEN must be set in .env file"
        )

    try:
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}
        ) as client:
            session_res = await client.get("https://api.fastmail.com/jmap/session")
            session_res.raise_for_status()
            session = session_res.json()
            api_url = session["apiUrl"]
            account_id = session["primaryAccounts"]["urn:ietf:params:jmap:submission"]

            # Get identity
            identities_res = await _call_jmap(
                client,
                api_url,
                using=["urn:ietf:params:jmap:submission"],
                calls=[["Identity/get", {"accountId": account_id}, "i1"]],
            )
            identity_id = identities_res[0][1]["list"][0]["id"]

            # Create and send email
            await _call_jmap(
                client,
                api_url,
                using=["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:submission"],
                calls=[
                    [
                        "EmailSubmission/set",
                        {
                            "accountId": account_id,
                            "create": {
                                "k1": {
                                    "identityId": identity_id,
                                    "subject": email.subject,
                                    "bodyValues": {"1": {"value": email.body}},
                                    "bodyStructure": {
                                        "partId": "1",
                                        "type": "text/plain",
                                    },
                                    "to": [{"email": r} for r in email.recipients],
                                }
                            },
                        },
                        "s1",
                    ]
                ],
            )

        return {"message": "Email has been sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")


@app.post("/scan-emails")
async def scan_emails():
    """
    Scans unread emails for WeTransfer links and marks them as read.
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "started",
    }

    def write_log():
        with log_lock:
            if EMAIL_SCAN_LOG_FILE.exists():
                with open(EMAIL_SCAN_LOG_FILE, "r") as f:
                    try:
                        log_entries = json.load(f)
                    except json.JSONDecodeError:
                        log_entries = []
            else:
                log_entries = []
            log_entries.append(log_entry)
            with open(EMAIL_SCAN_LOG_FILE, "w") as f:
                json.dump(log_entries, f, indent=2)

    token = os.getenv("FASTMAIL_API_TOKEN")
    if token:
        token = token.strip()

    if not token:
        log_entry["status"] = "failed"
        log_entry["error_message"] = "FASTMAIL_API_TOKEN must be set in .env file"
        write_log()
        raise HTTPException(
            status_code=500, detail="FASTMAIL_API_TOKEN must be set in .env file"
        )

    try:
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}
        ) as client:
            session_res = await client.get("https://api.fastmail.com/jmap/session")
            session_res.raise_for_status()
            session = session_res.json()
            api_url = session["apiUrl"]
            account_id = session["primaryAccounts"]["urn:ietf:params:jmap:mail"]
            log_entry["jmap_session"] = "success"

            config = get_config()
            sender_emails = config.sender_emails
            log_entry["config_sender_emails"] = sender_emails

            filter_condition: Dict[str, Any] = {"notKeyword": "$seen"}

            if sender_emails:
                from_conditions = []
                for email in sender_emails:
                    if email.startswith("*@"):
                        domain = email[2:]
                        from_conditions.append({"from": f"@{domain}"})
                    else:
                        from_conditions.append({"from": email})

                # JMAP doesn't support single-condition OR, so handle 1 email separately
                if len(from_conditions) == 1:
                    filter_condition = {
                        "operator": "AND",
                        "conditions": [{"notKeyword": "$seen"}, from_conditions[0]],
                    }
                elif len(from_conditions) > 1:
                    filter_condition = {
                        "operator": "AND",
                        "conditions": [
                            {"notKeyword": "$seen"},
                            {"operator": "OR", "conditions": from_conditions},
                        ],
                    }

            log_entry["jmap_filter"] = filter_condition

            # Find unread emails
            unread_res = await _call_jmap(
                client,
                api_url,
                using=["urn:ietf:params:jmap:mail"],
                calls=[
                    [
                        "Email/query",
                        {
                            "accountId": account_id,
                            "filter": filter_condition,
                        },
                        "e1",
                    ]
                ],
            )
            unread_ids = unread_res[0][1]["ids"]
            log_entry["unread_email_ids"] = unread_ids

            if not unread_ids:
                log_entry["status"] = "success"
                log_entry["message"] = "No unread emails found."
                log_entry["urls"] = []
                write_log()
                return {"message": "No unread emails found.", "urls": []}

            # Fetch emails
            emails_res = await _call_jmap(
                client,
                api_url,
                using=["urn:ietf:params:jmap:mail"],
                calls=[
                    [
                        "Email/get",
                        {
                            "accountId": account_id,
                            "ids": unread_ids,
                            "properties": [
                                "id",
                                "subject",
                                "from",
                                "bodyValues",
                                "bodyStructure",
                            ],
                            "fetchTextBodyValues": True,
                            "fetchHTMLBodyValues": True,
                        },
                        "e2",
                    ]
                ],
            )
            emails = emails_res[0][1]["list"]
            log_entry["fetched_emails_summary"] = [
                {
                    "id": e.get("id"),
                    "subject": e.get("subject"),
                    "from": e.get("from"),
                    "bodyStructure": e.get("bodyStructure"),
                }
                for e in emails
            ]

            # Extract links
            found_urls = []
            scanned_contents = []
            url_pattern = re.compile(r"https?://(?:we\.tl|wetransfer\.com)/[a-zA-Z0-9\-\_/]+")
            for email in emails:
                email_bodies = []
                body_values = email.get("bodyValues", {})
                text_parts = _find_text_parts(email.get("bodyStructure"))

                for part in text_parts:
                    part_id = part["partId"]
                    part_type = part["type"]
                    if part_id in body_values:
                        body_value = body_values[part_id].get("value", "")
                        email_bodies.append(body_value)

                        if part_type == "text/html":
                            soup = BeautifulSoup(body_value, "html.parser")
                            for a in soup.find_all("a", href=True):
                                href = a["href"]
                                if url_pattern.match(href):
                                    found_urls.append(href)
                        else:  # text/plain
                            urls = url_pattern.findall(body_value)
                            found_urls.extend(urls)

                scanned_contents.append(
                    {"email_id": email.get("id"), "bodies": email_bodies}
                )

            log_entry["scanned_contents"] = scanned_contents
            log_entry["found_urls_before_unique"] = found_urls

            # Mark as read
            await _call_jmap(
                client,
                api_url,
                using=["urn:ietf:params:jmap:mail"],
                calls=[
                    [
                        "Email/set",
                        {
                            "accountId": account_id,
                            "update": {
                                id: {"keywords/$seen": True} for id in unread_ids
                            },
                        },
                        "e3",
                    ]
                ],
            )
            log_entry["marked_as_read"] = unread_ids

    except Exception as e:
        log_entry["status"] = "failed"
        log_entry["error_message"] = f"Failed to scan emails: {e}"
        write_log()
        raise HTTPException(status_code=500, detail=f"Failed to scan emails: {e}")

    unique_urls = sorted(list(set(found_urls)))
    log_entry["status"] = "success"
    log_entry["urls"] = unique_urls
    log_entry["message"] = f"Found {len(unique_urls)} new WeTransfer links."
    write_log()
    return {
        "message": f"Found {len(unique_urls)} new WeTransfer links.",
        "urls": unique_urls,
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
                    "files": entry.get("files", []),
                }

        files_before = set(os.listdir(DOWNLOADS_DIR))
        log_entry = {
            "url": request.url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

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

            log_entry["transferwee_output"] = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            if result.returncode != 0:
                error_message = f"Download failed: {result.stderr or result.stdout}"
                log_entry["status"] = "failed"
                log_entry["error_message"] = error_message
                log_entries.append(log_entry)
                with open(DOWNLOAD_LOG_FILE, "w") as f:
                    json.dump(log_entries, f, indent=2)
                raise HTTPException(status_code=500, detail=error_message)

            files_after = set(os.listdir(DOWNLOADS_DIR))
            new_files = sorted(list(files_after - files_before))

            log_entry["status"] = "success"
            log_entry["files"] = new_files
            log_entry["file_details"] = [
                {"name": f, "size": os.path.getsize(DOWNLOADS_DIR / f)}
                for f in new_files
            ]

            config = get_config()
            copied_files = []
            if config.download_directory and new_files:
                dest_dir = Path(config.download_directory)
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for file_name in new_files:
                        source_path = DOWNLOADS_DIR / file_name
                        dest_path = dest_dir / file_name
                        shutil.copy2(source_path, dest_path)
                        copied_files.append(str(dest_path))
                    log_entry["copied_to"] = copied_files
                except Exception as e:
                    log_entry["copy_error"] = f"Failed to copy files: {e}"

            log_entries.append(log_entry)
            with open(DOWNLOAD_LOG_FILE, "w") as f:
                json.dump(log_entries, f, indent=2)

            response_payload = {
                "message": f"Download completed for {request.url}",
                "downloaded_files": new_files,
                "output": result.stdout,
            }
            if copied_files:
                response_payload["copied_files"] = copied_files
            return response_payload
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            log_entry["status"] = "failed"
            log_entry["error_message"] = f"An unexpected error occurred: {e}"
            log_entries.append(log_entry)
            with open(DOWNLOAD_LOG_FILE, "w") as f:
                json.dump(log_entries, f, indent=2)
            raise HTTPException(
                status_code=500, detail=f"An unexpected error occurred: {e}"
            )

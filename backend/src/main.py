import asyncio
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import re
import httpx
from bs4 import BeautifulSoup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
log_lock = asyncio.Lock()
graph_lock = asyncio.Lock()
config_lock = asyncio.Lock()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_json(self, client_id: str, data: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)

    async def broadcast_json(self, data: dict):
        for connection in self.active_connections.values():
            try:
                await connection.send_json(data)
            except Exception:
                # Ignore errors on send, connection might be closed
                pass


manager = ConnectionManager()
scheduler = AsyncIOScheduler()


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


class ProjectType(str, Enum):
    livework = "livework"
    turbosort = "turbosort"


class ZeusProject(BaseModel):
    name: str
    path: str
    type: str
    automationConfigId: str
    automationConfigName: str
    scanHostId: str
    scanHostAlias: str


class DownloadRequest(BaseModel):
    url: str
    client_id: str | None = None
    project_node_id: str | None = None


class Config(BaseModel):
    sender_emails: List[str] = []
    download_directory: str | None = None


class EmailSchema(BaseModel):
    recipients: list[EmailStr]
    subject: str
    body: str


async def get_config() -> Config:
    async with config_lock:
        if not CONFIG_FILE.exists():
            return Config()
        with open(CONFIG_FILE, "r") as f:
            try:
                return Config(**json.load(f))
            except (json.JSONDecodeError, TypeError):
                return Config()


async def save_config(config: Config):
    async with config_lock:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config.dict(), f, indent=2)


@app.get("/config", response_model=Config)
async def get_config_endpoint():
    """
    Retrieves the application configuration.
    """
    return await get_config()


@app.post("/config")
async def save_config_endpoint(config: Config):
    """
    Saves the application configuration.
    """
    await save_config(config)
    return {"message": "Configuration saved"}


@app.get("/")
def read_root():
    return {"message": "Backend for wetransfer-grab is running."}


@app.get("/graph", response_model=GraphState)
async def get_graph() -> GraphState:
    """
    Retrieves the graph state from a JSON file.
    """
    async with graph_lock:
        if not GRAPH_STATE_FILE.exists():
            return GraphState(nodes=[], edges=[])
        with open(GRAPH_STATE_FILE, "r") as f:
            try:
                data = json.load(f)
                return GraphState(**data)
            except (json.JSONDecodeError, TypeError):
                return GraphState(nodes=[], edges=[])


@app.post("/graph")
async def save_graph(graph_state: GraphState):
    """
    Saves the graph state to a JSON file.
    """
    async with graph_lock:
        with open(GRAPH_STATE_FILE, "w") as f:
            json.dump(graph_state.dict(), f, indent=2)
    return {"message": "Graph state saved"}


@app.get("/projects/discover", response_model=List[ZeusProject])
async def discover_projects(
    types: List[ProjectType] | None = Query(None), name: str | None = Query(None)
):
    """
    Retrieves a list of discovered projects from ProjectZeus.
    PROJECTZEUS_ADDRESS should be set to the host and port (e.g., http://host:port).
    """
    projectzeus_address = os.getenv("PROJECTZEUS_ADDRESS")
    if not projectzeus_address:
        raise HTTPException(
            status_code=500, detail="PROJECTZEUS_ADDRESS must be set in .env file"
        )

    try:
        async with httpx.AsyncClient() as client:
            url = f"{projectzeus_address.rstrip('/')}/api/projects"
            print(f"Contacting ProjectZeus at: {url}")
            response = await client.get(url)
            response.raise_for_status()
            projects_data = response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=(
                "ProjectZeus returned an error: "
                f"status_code={e.response.status_code}, response={e.response.text}"
            ),
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502, detail=f"Could not connect to ProjectZeus: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred while fetching projects: {e}"
        )

    try:
        projects = [ZeusProject(**p) for p in projects_data]
    except Exception:
        raise HTTPException(
            status_code=500, detail="Received invalid project data from ProjectZeus."
        )

    ignore_label = os.getenv("PROJECTZEUS_IGNORE_LABEL")
    if ignore_label:
        projects = [p for p in projects if p.name.lower() != ignore_label.lower()]

    if name:
        projects = [p for p in projects if name.lower() in p.name.lower()]

    if types:
        projects = [p for p in projects if p.type in types]

    # Deduplicate based on path, preserving order
    unique_projects: Dict[str, ZeusProject] = {}
    for project in projects:
        if project.path not in unique_projects:
            unique_projects[project.path] = project

    return list(unique_projects.values())


@app.websocket("/ws/progress/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(client_id)


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




async def _get_links_from_emails(sender_emails: List[str]) -> List[Dict[str, Any]]:
    """
    Internal logic to scan emails and return found links.
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "started",
    }

    # Load already processed email IDs from the log to avoid reprocessing
    processed_email_ids = set()
    if EMAIL_SCAN_LOG_FILE.exists():
        with open(EMAIL_SCAN_LOG_FILE, "r") as f:
            try:
                log_entries = json.load(f)
                for entry in log_entries:
                    # For backward compatibility, check old keys too
                    processed_email_ids.update(entry.get("processed_email_ids", []))
                    processed_email_ids.update(entry.get("marked_as_read", []))
                    processed_email_ids.update(entry.get("unread_email_ids", []))
            except json.JSONDecodeError:
                pass  # Log file might be empty or corrupted

    async def write_log():
        async with log_lock:
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
        await write_log()
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

            log_entry["config_sender_emails"] = sender_emails

            if not sender_emails:
                log_entry["status"] = "success"
                log_entry["message"] = "No sender emails provided."
                log_entry["urls"] = []
                await write_log()
                return []

            from_conditions = []
            for email in sender_emails:
                if email.startswith("*@"):
                    domain = email[2:]
                    from_conditions.append({"from": f"@{domain}"})
                else:
                    from_conditions.append({"from": email})

            if len(from_conditions) == 1:
                filter_condition: Dict[str, Any] = from_conditions[0]
            else:
                filter_condition = {"operator": "OR", "conditions": from_conditions}

            log_entry["jmap_filter"] = filter_condition

            # Find all matching emails
            email_query_res = await _call_jmap(
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
            all_found_ids = email_query_res[0][1]["ids"]
            ids_to_process = [
                eid for eid in all_found_ids if eid not in processed_email_ids
            ]

            log_entry["all_found_ids"] = all_found_ids
            log_entry["processed_email_ids"] = ids_to_process

            if not ids_to_process:
                log_entry["status"] = "success"
                log_entry["message"] = "No new emails to process."
                log_entry["urls"] = []
                await write_log()
                return []

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
                            "ids": ids_to_process,
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
            found_links = []
            scanned_contents = []
            url_pattern = re.compile(r"https?://(?:we\.tl|wetransfer\.com)/[a-zA-Z0-9\-\_/]+")
            for email in emails:
                sender_email = (email.get("from") or [{}])[0].get("email")
                if not sender_email:
                    continue

                email_bodies = []
                body_values = email.get("bodyValues", {})
                text_parts = _find_text_parts(email.get("bodyStructure"))

                urls_in_email = []
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
                                    urls_in_email.append(href)
                        else:  # text/plain
                            urls = url_pattern.findall(body_value)
                            urls_in_email.extend(urls)

                unique_urls = sorted(list(set(urls_in_email)))
                for i, url in enumerate(unique_urls):
                    found_links.append(
                        {
                            "url": url,
                            "sender": sender_email,
                            "subject": email.get("subject", "No Subject"),
                            "emailId": email.get("id"),
                            "linkIndex": i + 1,
                            "totalLinks": len(unique_urls),
                        }
                    )

                scanned_contents.append(
                    {"email_id": email.get("id"), "bodies": email_bodies}
                )

            log_entry["scanned_contents"] = scanned_contents
            log_entry["found_urls_before_unique"] = [link["url"] for link in found_links]

    except Exception as e:
        log_entry["status"] = "failed"
        log_entry["error_message"] = f"Failed to scan emails: {e}"
        await write_log()
        raise HTTPException(status_code=500, detail=f"Failed to scan emails: {e}")

    unique_links_dict = {link["url"]: link for link in reversed(found_links)}
    unique_links = sorted(list(unique_links_dict.values()), key=lambda x: x["url"])

    log_entry["status"] = "success"
    log_entry["urls"] = [link["url"] for link in unique_links]
    log_entry["links"] = unique_links
    log_entry["message"] = f"Found {len(unique_links)} new WeTransfer links."
    await write_log()
    return unique_links


@app.get("/scan-emails")
async def scan_emails(sender_emails: List[str] = Query([])):
    """
    Scans emails for WeTransfer links, ignoring previously processed emails.
    """
    links = await _get_links_from_emails(sender_emails)
    return {
        "message": f"Found {len(links)} new WeTransfer links.",
        "links": links,
    }


async def _download_link(
    url: str, project_node_id: str | None, client_id: str | None
):
    """
    Internal logic to download a single link.
    """
    async def send_progress(message_type: str, **kwargs):
        data = {"type": message_type, "url": url, **kwargs}
        if client_id:
            await manager.send_json(client_id, data)
        else:
            await manager.broadcast_json(data)

    await send_progress("status", status="started", message="Download process started.")

    async with log_lock:
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
            if entry.get("url") == url:
                message = "URL already downloaded"
                await send_progress(
                    "status",
                    status="skipped",
                    message=message,
                    files=entry.get("files", []),
                )
                return

        files_before = set(os.listdir(DOWNLOADS_DIR))
        log_entry = {
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            transferwee_script_path = transferwee_dir / "transferwee.py"
            python_executable = sys.executable

            proc = await asyncio.create_subprocess_exec(
                python_executable,
                str(transferwee_script_path),
                "download",
                url,
                cwd=DOWNLOADS_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_lines = []
            if proc.stdout:
                async for line in proc.stdout:
                    decoded_line = line.decode().strip()
                    stdout_lines.append(decoded_line)
                    await send_progress("log", message=decoded_line)

            stderr_lines = []
            if proc.stderr:
                async for line in proc.stderr:
                    decoded_line = line.decode().strip()
                    stderr_lines.append(decoded_line)
                    await send_progress("log", message=f"ERROR: {decoded_line}")

            await proc.wait()

            stdout = "\n".join(stdout_lines)
            stderr = "\n".join(stderr_lines)

            log_entry["transferwee_output"] = {
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }

            if proc.returncode != 0:
                error_message = f"Download failed: {stderr or stdout}"
                log_entry["status"] = "failed"
                log_entry["error_message"] = error_message
                log_entries.append(log_entry)
                with open(DOWNLOAD_LOG_FILE, "w") as f:
                    json.dump(log_entries, f, indent=2)
                await send_progress("status", status="failed", message=error_message)
                raise HTTPException(status_code=500, detail=error_message)

            files_after = set(os.listdir(DOWNLOADS_DIR))
            new_files = sorted(list(files_after - files_before))

            log_entry["status"] = "success"
            log_entry["files"] = new_files
            log_entry["file_details"] = [
                {"name": f, "size": os.path.getsize(DOWNLOADS_DIR / f)}
                for f in new_files
            ]

            config = await get_config()
            copied_files = []
            if project_node_id and new_files:
                graph = await get_graph()
                project_node = next(
                    (n for n in graph.nodes if n.id == project_node_id), None
                )

                if (
                    project_node
                    and project_node.data.get("label")
                    and config.download_directory
                ):
                    project_folder_name = project_node.data["label"]
                    project_type = project_node.data.get("projectType", "turbosort")
                    dest_dir = (
                        Path(config.download_directory)
                        / project_folder_name
                        / project_type
                    )

                    try:
                        dest_dir.mkdir(parents=True, exist_ok=True)

                        # Create .<type> file
                        type_file_path = dest_dir / f".{project_type}"
                        with open(type_file_path, "w") as f:
                            f.write(project_folder_name)

                        for file_name in new_files:
                            source_path = DOWNLOADS_DIR / file_name
                            dest_path = dest_dir / file_name
                            shutil.copy2(source_path, dest_path)
                            copied_files.append(str(dest_path))
                        log_entry["copied_to"] = copied_files
                        await send_progress(
                            "log", message=f"Copied files to {dest_dir}"
                        )
                    except Exception as e:
                        log_entry["copy_error"] = f"Failed to copy files: {e}"
                        await send_progress(
                            "log", message=f"ERROR: Failed to copy files: {e}"
                        )

            log_entries.append(log_entry)
            with open(DOWNLOAD_LOG_FILE, "w") as f:
                json.dump(log_entries, f, indent=2)

            response_payload = {
                "message": f"Download completed for {url}",
                "downloaded_files": new_files,
                "output": stdout,
            }
            if copied_files:
                response_payload["copied_files"] = copied_files

            await send_progress(
                "status", status="success", message="Download successful", **response_payload
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            error_message = f"An unexpected error occurred: {e}"
            log_entry["status"] = "failed"
            log_entry["error_message"] = error_message
            log_entries.append(log_entry)
            with open(DOWNLOAD_LOG_FILE, "w") as f:
                json.dump(log_entries, f, indent=2)
            await send_progress("status", status="failed", message=error_message)
            # Don't raise HTTPException in internal function, just log and return
            print(f"Error downloading {url}: {error_message}")


@app.post("/download")
async def download_url(request: DownloadRequest):
    """
    Downloads files from a WeTransfer URL using the transferwee script
    and logs the download. Prevents re-downloading of the same URL.
    Streams progress over WebSocket if client_id is provided.
    """
    await _download_link(
        url=request.url,
        project_node_id=request.project_node_id,
        client_id=request.client_id,
    )
    return {"message": "Download process initiated."}


async def scheduled_job():
    print("Running scheduled scan...")
    graph = await get_graph()

    email_nodes = {
        n.id: n.data.get("label") for n in graph.nodes if n.data.get("nodeType") == "email"
    }
    project_nodes = {n.id for n in graph.nodes if n.data.get("nodeType") == "project-folder"}

    rules: Dict[str, List[str]] = {}
    for edge in graph.edges:
        if edge.source in email_nodes and edge.target in project_nodes:
            email = email_nodes[edge.source]
            if email and "@" in email:
                if email not in rules:
                    rules[email] = []
                rules[email].append(edge.target)

    if not rules:
        print("Scheduler: No rules configured. Skipping.")
        return

    all_emails = list(rules.keys())
    found_links = await _get_links_from_emails(all_emails)

    if not found_links:
        print("Scheduler: No new links found.")
        return

    print(f"Scheduler: Found {len(found_links)} new links. Starting downloads.")
    for link in found_links:
        sender = link["sender"]
        if sender in rules:
            for project_id in rules[sender]:
                await _download_link(
                    url=link["url"], project_node_id=project_id, client_id=None
                )


@app.on_event("startup")
async def startup_event():
    scheduler.add_job(scheduled_job, "interval", minutes=3)
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

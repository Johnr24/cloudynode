# ☁️🥰 CloudyNode 🥰☁️

CloudyNode is a tool to automate your file downloading workflow. It scans your emails for download links (like WeTransfer), downloads the files, and organizes them into project folders for you. All of this is configured through a simple and intuitive node-based interface in your browser.


## The Problem

Do you receive files from clients via services like WeTransfer? Manually downloading and sorting these files every day is tedious and time-consuming. It's a repetitive task that can be automated, freeing you up to focus on more important work.

## The Plan: CloudyNode
<img src="readme/nathan.png" alt="image" class="custom-image" width=500>

CloudyNode provides a visual way to automate this process:

- **Email Scanning:** Automatically scans emails from specified senders for download links.
- **Automated Downloads:** Uses `transferwee` to download files from WeTransfer links.
- **Visual Workflow Editor:** A node-based UI (like in DaVinci Resolve or Blender) lets you define where files should go. You can link specific email senders to specific project folders.
- **Real-time Feedback:** See download progress in real-time directly in the UI.

## How It Works

CloudyNode consists of two main parts:

- **Backend:** A Python FastAPI application that:
    - Scans emails using the JMAP protocol.
    - Manages download tasks.
    - Uses `transferwee` to handle WeTransfer downloads.
    - Serves the workflow graph configuration.
    - Pushes real-time progress updates over WebSockets.
- **Frontend:** A React application (built with Vite) that provides:
    - A `react-flow` powered node editor to build your download workflows.
    - A clean interface to monitor download status.

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/).
- A JMAP-enabled email account (e.g., Fastmail).

### Installation

1.  **Configure your environment:**
    -   From the root of the project directory, create a `.env` file by copying the template:
        ```bash
        cp env.template .env
        ```
    -   Edit `.env` and fill in your JMAP credentials and other settings. You'll need:
        -   `JMAP_URL`: The JMAP API endpoint for your email provider.
        -   `JMAP_TOKEN`: An API token for authentication.
        -   `PROJECTS_BASE_PATH`: The base directory on your local machine where your project folders are located.

2.  **Run the application:**
    The easiest way to get started is with Docker Compose. This will build and run both the frontend and backend services from the root of the project:
    ```bash
    docker-compose up --build
    ```

3.  **Access CloudyNode:**
    -   Open your web browser and navigate to `http://localhost:5173`.

## Usage

1.  **Add an Email Source:**
    -   Right-click on the canvas and select "Add Email Source".
    -   Enter the email address of a sender whose links you want to download automatically.

2.  **Add a Project Folder:**
    -   Right-click and select "Add Project Folder".
    -   Start typing the name of a project. The application will autocomplete based on the folders found in your `PROJECTS_BASE_PATH`.
    -   Select the desired project folder.

3.  **Connect the Nodes:**
    -   Drag a connection from the output of the Email Source node to the input of the Project Folder node.

4.  **Start Scanning:**
    -   The backend will periodically scan for new emails from the configured senders. When a new email with a WeTransfer link is found, the download will begin automatically.

Now, any WeTransfer links from that sender will be downloaded and saved into the specified project folder. Enjoy your new automated workflow!

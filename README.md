# Darwin

<p align="center">
  <strong>An autonomous, general-purpose agentic execution engine — inspired by Claude Code and Hermes Agent.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-blue?logo=python&logoColor=white" alt="Python >= 3.11" />
  <img src="https://img.shields.io/badge/orchestrator-LangGraph-1C3C3C?logo=langchain&logoColor=white" alt="LangGraph" />
  <img src="https://img.shields.io/badge/protocol-MCP%20(stdio)-orange" alt="MCP" />
  <img src="https://img.shields.io/badge/memory-Qdrant%20%2B%20Neo4j%20(mem0)-purple" alt="Memory" />
  <img src="https://img.shields.io/badge/sandbox-Docker%20%2B%20Lima-2496ED?logo=docker&logoColor=white" alt="Sandbox" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT" />
</p>

<p align="center">
  <img src="assets/tui-preview.svg" alt="Darwin TUI (tokyo-night theme — 13 MCP servers, 135 MCP tools, 14 native tools)" width="100%" />
</p>

**Darwin** is an autonomous, model-agnostic agentic execution engine built on a custom **LangGraph `StateGraph`** reasoning loop. It plans before acting, navigates local file systems within strict workspace boundaries, executes untrusted multi-language code inside hardened Docker or Lima sandboxes, connects to external tools via the **Model Context Protocol (MCP)** (`13` servers / `135` MCP tools + `14` native tools) with dynamic **Tool RAG** masking, and enforces deterministic guardrails alongside **Human-in-the-Loop (HITL)** approval gates.

---

## Table of Contents

1. [Highlights & Core Capabilities](#1-highlights--core-capabilities)
2. [System Architecture & Flowcharts](#2-system-architecture--flowcharts)
   - [High-Level System Architecture](#21-high-level-system-architecture)
   - [LangGraph Turn & Two-Stage Safety/HITL Pipeline](#22-langgraph-turn--two-stage-safetyhitl-pipeline)
   - [Hybrid Memory & Dynamic Tool RAG Flow](#23-hybrid-memory--dynamic-tool-rag-flow)
3. [Prerequisites](#3-prerequisites)
   - [Core Runtime & Toolchains](#31-core-runtime--toolchains)
   - [Backing Infrastructure Services](#32-backing-infrastructure-services)
   - [Sandbox Runtime Images](#33-sandbox-runtime-images)
   - [API Keys & Optional Credentials](#34-api-keys--optional-credentials)
4. [Quick Start & Installation](#4-quick-start--installation)
5. [Subsystems Deep Dive](#5-subsystems-deep-dive)
   - [Native Tools (Category B)](#51-native-tools-category-b)
   - [MCP Subsystem (Category A) & Tool RAG](#52-mcp-subsystem-category-a--tool-rag)
   - [Hardened Multi-Language Execution Sandbox](#53-hardened-multi-language-execution-sandbox)
   - [Security, Guardrails & Permission Model](#54-security-guardrails--permission-model)
   - [Hybrid Tiered Memory Architecture](#55-hybrid-tiered-memory-architecture)
6. [Terminal UI (TUI) & Diagnostic CLIs](#6-terminal-ui-tui--diagnostic-clis)
7. [Configuration Reference](#7-configuration-reference)
8. [Repository Layout](#8-repository-layout)
9. [Implementation Roadmap & Status](#9-implementation-roadmap--status)
10. [License & Author](#10-license--author)

---

## 1. Highlights & Core Capabilities

| Capability | Implementation Stack | Details |
| :--- | :--- | :--- |
| **Reasoning Engine** | `LangGraph` (`StateGraph`) | Plan-first tool-calling loop with message upsert reducers, 50-message sliding buffer, and a 12-round tool loop guard. |
| **Model Agnostic** | `langchain-openai` (`ChatOpenAI`) | Connects to any OpenAI-compatible endpoint (`OpenAI`, `DeepSeek`, local `vLLM`, `Ollama`) via `DARWIN_LLM_BASE_URL`, `DARWIN_LLM_API_KEY`, and `DARWIN_LLM_MODEL`. |
| **Durable Sessions** | `PostgreSQL 16` (`AsyncPostgresSaver`) | Thread checkpoints persist across process restarts; sessions are auto-slugified from the user's first message (e.g., `git-status-repo`). |
| **Hybrid Memory** | `mem0` + `Qdrant` + `Neo4j 5` | Combines short-term state buffers with long-term vector episodic memory (`Qdrant`) and entity-relationship knowledge graphs (`Neo4j`). |
| **Local Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | Runs locally (384 dimensions) for both episodic memory and Tool RAG—zero external embedding API cost and offline cache support. |
| **Tool RAG** | `Qdrant` (`tools_registry`) + Lexical Union | Prevents context window saturation across `135` MCP tools by indexing tool schemas and dynamically binding only the top-K (`12`) semantic hits + up to `4` lexical matches per turn. |
| **Two-Stage HITL & Scope Gate** | `LangGraph interrupt()` + `permissions.json` | Enforces workspace boundaries (`1/2/3` JIT escalation for once/session/deny) and human approval (`y/n`) on mutating calls with macOS `osascript` desktop notifications. |
| **Deterministic Guardrails** | `Pydantic` + Regex Interceptors | Blocks prompt injection patterns, bans destructive shell commands (`rm -rf`, `mkfs`, fork bombs, `dd`), scrubs secret env vars from child shells, and redacts PII/tokens/keys. |
| **Execution Sandbox** | `Docker` (default) + `Lima VM` (opt-in) | Runs Bash, Python, Node, Bun, Go, Rust, C++, and Java in locked-down containers (`--read-only`, `--network=none`, `--cap-drop=ALL`, `no-new-privileges`, resource limits). |
| **Async Task Queue** | `Valkey 8` / `Redis` + `RQ` | `TaskQueue` wrapper ready to offload non-blocking background jobs from the main reasoning loop. |
| **Rich Terminal UI** | `rich` + `prompt_toolkit` | Opencode-style boxed input prompt, slash-command autocompletion, arrow-key session & theme pickers, tool call/result traces, and 5 color themes. |

---

## 2. System Architecture & Flowcharts

### 2.1 High-Level System Architecture

```mermaid
flowchart TB
    subgraph Client["Terminal UI Layer (src/darwin/tui.py & main.py)"]
        User(["👤 User"])
        TUI["Rich + prompt_toolkit TUI<br/>Slash Commands · Pickers · Tool Traces"]
        Notify["macOS Desktop Notifications<br/>(osascript / stderr fallback)"]
    end

    subgraph Core["Core Orchestration & State (src/darwin/core/)"]
        Graph["LangGraph StateGraph<br/>(orchestrator.py)"]
        Guard["Deterministic Guardrails<br/>Input Sanitizer · Secret Redactor · Command Policy"]
        LLM["Model-Agnostic LLM Client<br/>(OpenAI / DeepSeek / vLLM / Ollama)"]
        Queue["TaskQueue (queue.py)<br/>Async Job Offloading"]
    end

    subgraph Storage["Persistence, Memory & Queues (docker-compose.yml)"]
        PG[("PostgreSQL 16<br/>AsyncPostgresSaver<br/>Durable Checkpoints")]
        Mem0["mem0 MemoryClient<br/>(all-MiniLM-L6-v2 384d)"]
        Qdrant[("Qdrant Vector DB<br/>• memories collection<br/>• tools_registry collection")]
        Neo4j[("Neo4j 5 / Aura<br/>Knowledge Graph Store")]
        Valkey[("Valkey 8 / Redis<br/>RQ Broker")]
    end

    subgraph Tooling["Tooling & Execution Layer"]
        ToolRAG["Tool RAG Selector<br/>(tools/registry.py)<br/>Top-12 Vector + 4 Lexical"]
        NativeTools["14 Native Tools (Category B)<br/>Filesystem · Shell · Docs · Email · Memory · Notify"]
        MCPClient["Stdio MCP Client & Bridge<br/>(mcp/client.py & adapters.py)<br/>13 Servers · 135 MCP Tools"]
        Sandbox["Multi-Runtime Sandbox (sandbox/)<br/>Hardened Docker Containers & Lima VM"]
    end

    User <-->|"Interactive Prompt / Approvals"| TUI
    TUI <-->|"Stream Updates & Command(resume)"| Graph
    Graph -.->|"Trigger Alert"| Notify
    Notify -.->|"Visual Banner"| User

    Graph <-->|"Sanitize & Redact"| Guard
    Graph <-->|"Bind Selected Tools & Invoke"| LLM
    Graph <-->|"Save / Load Thread State"| PG
    Graph <-->|"Recall Context / Save Turn"| Mem0
    Graph -->|"Enqueue Jobs"| Queue
    Queue --> Valkey

    Mem0 <-->|"Episodic Vectors"| Qdrant
    Mem0 <-->|"Entity Graph"| Neo4j

    Graph <-->|"Query User Intent"| ToolRAG
    ToolRAG <-->|"Cosine Search"| Qdrant
    Graph <-->|"Execute Approved Calls"| NativeTools
    Graph <-->|"Execute Approved server__tool"| MCPClient
    NativeTools <-->|"run_sandboxed / run_code"| Sandbox

    classDef sandbox fill:#ff8a3d,stroke:#d35400,color:#1a1a1a,stroke-width:2px;
    class Sandbox sandbox;

    linkStyle 0 stroke:#e74c3c,stroke-width:3px;
    linkStyle 1 stroke:#f39c12,stroke-width:3px;
    linkStyle 2 stroke:#f1c40f,stroke-width:3px;
    linkStyle 3 stroke:#e67e22,stroke-width:3px;
    linkStyle 4 stroke:#e91e63,stroke-width:3px;
    linkStyle 5 stroke:#1abc9c,stroke-width:3px;
    linkStyle 6 stroke:#3498db,stroke-width:3px;
    linkStyle 7 stroke:#9b59b6,stroke-width:3px;
    linkStyle 8 stroke:#ff7043,stroke-width:3px;
    linkStyle 9 stroke:#d35400,stroke-width:3px;
    linkStyle 10 stroke:#8e44ad,stroke-width:3px;
    linkStyle 11 stroke:#16a085,stroke-width:3px;
    linkStyle 12 stroke:#00bcd4,stroke-width:3px;
    linkStyle 13 stroke:#2ecc71,stroke-width:3px;
    linkStyle 14 stroke:#27ae60,stroke-width:3px;
    linkStyle 15 stroke:#5dade2,stroke-width:3px;
    linkStyle 16 stroke:#ff8a3d,stroke-width:3px;
```

### 2.2 LangGraph Turn & Two-Stage Safety/HITL Pipeline

Every user message passes through a multi-stage state graph in `src/darwin/core/orchestrator.py` before any tool touches the host or external services:

```mermaid
flowchart TD
    Start(["START Turn"]) --> Trim["<b>guard (_trim_buffer)</b><br/>• Strip stored SystemMessages<br/>• Trim buffer to MAX_BUFFER_MESSAGES (50)"]
    Trim --> Sanitize["<b>agent (Pre-LLM Sanitization)</b><br/>• Check latest HumanMessage for prompt injection<br/>• Redact secrets/PII across history<br/>• Enforce MAX_TOOL_ROUNDS (12) loop guard"]

    Sanitize -->|Injection Detected| Blocked(["Return 'Blocked by input guardrails'"])
    Sanitize -->|Loop Limit Reached| LoopStop(["Stop & report after 12 tool rounds"])
    Sanitize -->|Clean| Select["<b>Dynamic Tool Binding</b><br/>• Always bind 14 Native Tools<br/>• Query Qdrant tools_registry for top-12 MCP tools<br/>• Union up to 4 lexical name matches"]

    Select --> InvokeLLM["<b>Invoke ChatOpenAI</b><br/>SystemPrompt + Recalled Memory Context + History<br/>Sanitize & wire-safe output"]
    InvokeLLM --> HasTools{"Emitted<br/>tool_calls?"}

    HasTools -->|No| EndTurn(["END Turn & Save to mem0"])
    HasTools -->|Yes| PermNode["<b>permissions (_permissions)</b><br/>Evaluate permissions.json + SessionScope"]

    PermNode --> PermDecision{"Policy Decision<br/>(decide)"}
    PermDecision -->|"deny (e.g. ~/.ssh, sudo rm)"| HardDeny["Return ToolMessage:<br/>Blocked by policy rule"]
    HardDeny --> Sanitize

    PermDecision -->|"ask (Outside WORKSPACE_ROOT<br/>or Bash(sudo *))"| Escalate["<b>LangGraph interrupt() + osascript</b><br/>Prompt User: [1] Once [2] Session [3] Deny"]
    Escalate -->|Denied| ScopeDeny["Return ToolMessage:<br/>Permission denied by user"]
    ScopeDeny --> Sanitize
    Escalate -->|"Approved (Update SessionScope)"| ApproveNode

    PermDecision -->|"allow (Inside workspace<br/>or allow rule)"| ApproveNode["<b>approve (_approve)</b><br/>Check Two-Tier Mutability (is_mutating)"]

    ApproveNode --> IsMutating{"Any Mutating<br/>Tool Call?"}
    IsMutating -->|"No (Tier 1 Read-Only)"| ExecTools["<b>tools (ToolNode)</b><br/>Execute Native or MCP Tool"]
    IsMutating -->|"Yes (Tier 2 Mutating)"| HITL["<b>LangGraph interrupt() + osascript</b><br/>Prompt User: approve tool_name? (y/n)"]

    HITL -->|"n (Denied)"| MutateDeny["Return ToolMessage:<br/>Denied by user"]
    MutateDeny --> Sanitize
    HITL -->|"y (Approved)"| ExecTools

    ExecTools --> Sanitize

    linkStyle 0 stroke:#3498db,stroke-width:3px;
    linkStyle 1 stroke:#5dade2,stroke-width:3px;
    linkStyle 2 stroke:#e74c3c,stroke-width:3px;
    linkStyle 3 stroke:#e67e22,stroke-width:3px;
    linkStyle 4 stroke:#2ecc71,stroke-width:3px;
    linkStyle 5 stroke:#1abc9c,stroke-width:3px;
    linkStyle 6 stroke:#9b59b6,stroke-width:3px;
    linkStyle 7 stroke:#00bcd4,stroke-width:3px;
    linkStyle 8 stroke:#f39c12,stroke-width:3px;
    linkStyle 9 stroke:#f1c40f,stroke-width:3px;
    linkStyle 10 stroke:#e74c3c,stroke-width:3px;
    linkStyle 11 stroke:#ec7063,stroke-width:3px;
    linkStyle 12 stroke:#ff8a3d,stroke-width:3px;
    linkStyle 13 stroke:#e74c3c,stroke-width:3px;
    linkStyle 14 stroke:#ec7063,stroke-width:3px;
    linkStyle 15 stroke:#2ecc71,stroke-width:3px;
    linkStyle 16 stroke:#27ae60,stroke-width:3px;
    linkStyle 17 stroke:#af7ac5,stroke-width:3px;
    linkStyle 18 stroke:#2ecc71,stroke-width:3px;
    linkStyle 19 stroke:#e91e63,stroke-width:3px;
    linkStyle 20 stroke:#e74c3c,stroke-width:3px;
    linkStyle 21 stroke:#ec7063,stroke-width:3px;
    linkStyle 22 stroke:#1abc9c,stroke-width:3px;
    linkStyle 23 stroke:#3498db,stroke-width:3px;
```

### 2.3 Hybrid Memory & Dynamic Tool RAG Flow

Darwin unifies all vector operations onto a single **Qdrant** instance using two isolated collections (`memories` and `tools_registry`) powered by the same local `sentence-transformers/all-MiniLM-L6-v2` (384-dim) embedding model:

```mermaid
flowchart LR
    subgraph Boot["Boot Phase (main.py)"]
        MCPJson["mcp.json<br/>(13 MCP Servers)"] --> Connect["MCPClient.connect_all()"]
        Connect --> Schemas["Extract 135 Tool Names<br/>& Descriptions"]
        Schemas --> EmbedBoot["all-MiniLM-L6-v2<br/>(384-dim Embeddings)"]
        EmbedBoot --> QdrantTools[("Qdrant<br/>Collection: tools_registry")]
    end

    subgraph Runtime["Per-Turn Runtime"]
        UserMsg["User Query"] --> EmbedQuery["Encode Query"]
        EmbedQuery --> QdrantTools
        QdrantTools -->|"Top-12 Cosine + 4 Lexical"| BoundTools["Bound Tools for Turn"]

        UserMsg --> MemRecall["MemoryClient.recall()"]
        MemRecall <--> QdrantMem[("Qdrant<br/>Collection: memories")]
        MemRecall <--> Neo4jGraph[("Neo4j<br/>Entity-Relationship Graph")]
        MemRecall -->|"Injected into SystemMessage"| AgentReply["Agent Execution & Reply"]
        AgentReply -->|"MemoryClient.add(user, reply)"| MemWrite["Extract Facts & Relationships"]
        MemWrite --> QdrantMem
        MemWrite --> Neo4jGraph
    end

    linkStyle 0 stroke:#f39c12,stroke-width:3px;
    linkStyle 1 stroke:#f1c40f,stroke-width:3px;
    linkStyle 2 stroke:#1abc9c,stroke-width:3px;
    linkStyle 3 stroke:#2ecc71,stroke-width:3px;
    linkStyle 4 stroke:#3498db,stroke-width:3px;
    linkStyle 5 stroke:#5dade2,stroke-width:3px;
    linkStyle 6 stroke:#00bcd4,stroke-width:3px;
    linkStyle 7 stroke:#9b59b6,stroke-width:3px;
    linkStyle 8 stroke:#e91e63,stroke-width:3px;
    linkStyle 9 stroke:#16a085,stroke-width:3px;
    linkStyle 10 stroke:#ff8a3d,stroke-width:3px;
    linkStyle 11 stroke:#e74c3c,stroke-width:3px;
    linkStyle 12 stroke:#8e44ad,stroke-width:3px;
    linkStyle 13 stroke:#27ae60,stroke-width:3px;
```

---

## 3. Prerequisites

Before installing and running Darwin, ensure your machine meets the following prerequisites.

### 3.1 Core Runtime & Toolchains

| Prerequisite | Version / Binary | Why It Is Required |
| :--- | :--- | :--- |
| **Python** | `>= 3.11` | Core runtime for Darwin, LangGraph, `mem0`, and Pydantic schemas. |
| **[uv](https://docs.astral.sh/uv/)** | `uv` & `uvx` (`>= 0.4+`) | **Required.** Manages the Python environment (`uv_build` backend) and spawns Python-based stdio MCP servers (`mcp-server-time`, `mcp-server-sqlite`, `mcp-server-fetch`, `mcp-server-git`, `mcp-server-docker`) via `uvx`. |
| **Node.js & npm** | `node >= 18` & `npx` | **Required for Node MCP servers.** Spawns `@modelcontextprotocol/server-sequential-thinking`, `server-filesystem`, `server-postgres`, `@playwright/mcp`, `firecrawl-mcp`, `exa-mcp-server`, and `@upstash/context7-mcp` via `npx -y`. |
| **Docker & Docker Compose** | `docker` & `docker compose` | **Required.** Runs the local backing services (`Postgres`, `Qdrant`, `Neo4j`, `Valkey`), the containerized GitHub MCP server (`ghcr.io/github/github-mcp-server`), and the default isolated code execution sandbox. |
| **Git** | `git` | Required for repository operations and `mcp-server-git`. |
| **[Lima](https://lima-vm.io/)** *(Optional)* | `limactl` (`v1` or `v2`) | Optional Linux VM fallback (`SANDBOX_BACKEND=lima`) when you want full VM isolation or when Docker is unavailable. Never auto-started unless explicitly requested. |
| **macOS `osascript`** *(Optional)* | Built-in on macOS | Powers native desktop notifications when Darwin pauses at an approval gate or calls `notify_user`. Gracefully falls back to `stderr` on Linux/other OSes. |

### 3.2 Backing Infrastructure Services

All four backing services are pre-configured in [`docker-compose.yml`](docker-compose.yml) with zero manual setup required:

1. **PostgreSQL 16** (`postgres:16` on port `5432`) — Stores durable LangGraph checkpoints (`checkpoints` table) and session metadata.
2. **Qdrant** (`qdrant/qdrant:latest` on port `6333`) — Stores 384-dimensional vectors for episodic memories (`memories`) and MCP tool schemas (`tools_registry`).
3. **Neo4j 5** (`neo4j:5` on ports `7687` Bolt / `7474` HTTP) — Stores structured entity-relationship graphs via `mem0ai[graph]`.
   - *Resource Note:* Local Neo4j requires **~1.5–2 GB RAM** for the JVM. On memory-constrained machines, you can point `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` in `.env` to a free [Neo4j Aura](https://neo4j.com/cloud/aura/) cloud instance instead.
4. **Valkey 8** (`valkey/valkey:8` on port `6379`) — Redis-compatible in-memory broker backing the `RQ` (`TaskQueue`) worker system.

> **Fault-Tolerant Boot:** While **PostgreSQL** and an **LLM endpoint** are required for the core loop, Darwin treats Qdrant/Neo4j (`mem0`), Tool RAG, and individual MCP servers as graceful enhancements—if Qdrant or an MCP server is down or missing credentials, Darwin logs a notice and continues booting.

### 3.3 Sandbox Runtime Images

When the agent invokes `run_sandboxed` or `run_code` via the Docker backend, Docker pulls the corresponding language image on demand from a strict, hardcoded allowlist in [`src/darwin/sandbox/docker.py`](src/darwin/sandbox/docker.py):

| Language Key | Docker Image | Default Execution Runner (`run_code`) |
| :--- | :--- | :--- |
| `bash` | `alpine:3.20` | `sh /tmp/main.sh` |
| `python` | `python:3.12-slim` | `python /tmp/main.py` |
| `node` | `node:22-slim` | `node /tmp/main.js` |
| `bun` | `oven/bun:1` | `bun /tmp/main.ts` |
| `go` | `golang:1.23-alpine` | `go run /tmp/main.go` |
| `rust` | `rust:1.82-slim` | `rustc /tmp/main.rs -o /tmp/main && /tmp/main` |
| `cpp` | `gcc:14` | `g++ -std=c++17 /tmp/main.cpp -o /tmp/main && /tmp/main` |
| `java` | `eclipse-temurin:21-jdk` | `java /tmp/Main.java` |

### 3.4 API Keys & Optional Credentials

- **Required — LLM Provider:**
  - `DARWIN_LLM_BASE_URL` (e.g., `https://api.openai.com/v1`, `https://api.deepseek.com/v1`, or `http://localhost:11434/v1` for Ollama)
  - `DARWIN_LLM_API_KEY` (your provider API key)
  - `DARWIN_LLM_MODEL` (e.g., `gpt-4o-mini`, `gpt-4o`, `deepseek-chat`, etc.)
- **Optional — External MCP Servers & Email Tools:**
  - `GITHUB_PERSONAL_ACCESS_TOKEN`: Enables the `github` MCP server (`repos`, `issues`, `pull_requests` toolsets).
  - `FIRECRAWL_API_KEY`: Enables the `firecrawl` MCP server for web scraping and crawling.
  - `EXA_API_KEY`: Enables the `exa` neural web search MCP server.
  - `CONTEXT7_API_KEY`: Optional key for `@upstash/context7-mcp` to increase documentation rate limits.
  - `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`, `IMAP_HOST`, `IMAP_PORT`: Enables `email_read` and `email_send` (for Gmail, requires 2-Step Verification, IMAP enabled, and a 16-character App Password).

---

## 4. Quick Start & Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/The-Tourist-170/Darwin.git
cd Darwin
```

### Step 2: Configure Environment Variables

Copy the example environment file and configure your LLM provider (and any optional API keys):

```bash
cp .env.example .env
```

Edit `.env` with your model credentials:

```dotenv
DARWIN_LLM_BASE_URL=https://api.openai.com/v1
DARWIN_LLM_API_KEY=sk-your-api-key
DARWIN_LLM_MODEL=gpt-4o-mini
```

*(Also review [`mcp.json`](mcp.json) and update the hardcoded workspace path `/Users/kaneki/Dev/Darwin` under the `filesystem` and `sqlite` MCP server arguments if your repository lives at a different path.)*

### Step 3: Start the Backing Services

Launch PostgreSQL, Qdrant, Neo4j, and Valkey in the background:

```bash
docker compose up -d
```

### Step 4: Install Dependencies & Run Darwin

`uv` automatically creates the virtual environment, installs all dependencies from `pyproject.toml` (including downloading `sentence-transformers/all-MiniLM-L6-v2` on first run), and launches the Darwin TUI:

```bash
uv run darwin
```

---

## 5. Subsystems Deep Dive

### 5.1 Native Tools (Category B)

Built in-house under [`src/darwin/tools/`](src/darwin/tools/) and tightly coupled with Darwin's workspace scope, redaction engine, and LangGraph `interrupt()` gates:

| Tool Name | Module | Permission Tier | Description |
| :--- | :--- | :--- | :---
| `read_file` | `tools/filesystem.py` | **Tier 1 (Read-Only)** | Reads text files inside `WORKSPACE_ROOT` (up to `100,000` chars). Escalates via prompt if path is outside workspace. |
| `list_directory` | `tools/filesystem.py` | **Tier 1 (Read-Only)** | Lists sorted files and directories inside `WORKSPACE_ROOT`. |
| `write_file` | `tools/filesystem.py` | **Tier 2 (Mutating — HITL)** | Writes text to a file inside `WORKSPACE_ROOT`, creating parent directories as needed. |
| `parse_document` | `tools/documents.py` | **Tier 1 (Read-Only)** | Converts PDFs, Word (`.docx`), and Excel (`.xlsx`) files into clean Markdown using Microsoft `MarkItDown`. |
| `run_shell` | `tools/shell.py` | **Tier 2 (Mutating — HITL)** | Runs host shell commands via `subprocess.run` with timeout (`1–120s`), banned-command filtering, `8,000`-char output truncation, secret env scrubbing, and TTY forwarding for `sudo`. |
| `run_sandboxed` | `tools/sandbox.py` | **Tier 2 (Mutating — HITL)** | Runs a shell command inside an isolated language container (`bash`, `python`, `node`, `bun`, `go`, `rust`, `cpp`, `java`). Read-only workspace and no network by default. |
| `run_code` | `tools/sandbox.py` | **Tier 2 (Mutating — HITL)** | Writes a source code snippet to `/tmp/main.<ext>` inside the isolated sandbox container and executes it with the language's compiler/interpreter. |
| `sandbox_containers` | `tools/sandbox.py` | **Tier 1 (Read-Only)** | Lists all running or exited Docker containers carrying the `darwin.sandbox=1` ownership label. |
| `sandbox_stop` | `tools/sandbox.py` | **Tier 2 (Mutating — HITL)** | Stops and removes a Darwin-owned sandbox container (`label=darwin.sandbox=1`). Refuses to touch non-Darwin containers. |
| `email_read` | `tools/email.py` | **Tier 1 (Read-Only)** | Connects over `IMAP4_SSL` to fetch sender, subject, date, and 200-char plain-text snippets of recent inbox messages (`1–20`). |
| `email_send` | `tools/email.py` | **Tier 2 (Mutating — HITL)** | Sends email over `SMTP` (`STARTTLS`). Includes outbound leak protection that blocks sending if `redact(body) != body`. |
| `memory_recall` | `tools/memory_tool.py` | **Tier 1 (Read-Only)** | Explicitly queries `mem0` (Qdrant + Neo4j) for long-term episodic memories matching a search string. |
| `memory_save` | `tools/memory_tool.py` | **Tier 1 (Auto-Approved)** | Explicitly stores a verbatim fact into long-term memory across sessions. |
| `notify_user` | `tools/notify_user.py` | **Tier 1 (Auto-Approved)** | Sends a non-blocking macOS desktop notification via `osascript` (or `stderr` fallback). |

### 5.2 MCP Subsystem (Category A) & Tool RAG

Darwin connects to external **Model Context Protocol (MCP)** servers over **stdio** using an in-house `AsyncExitStack` client ([`src/darwin/mcp/client.py`](src/darwin/mcp/client.py)) and dynamically converts their JSON Schemas into Pydantic-validated LangChain `StructuredTool`s named `{server}__{tool}` ([`src/darwin/mcp/adapters.py`](src/darwin/mcp/adapters.py)). Across all `13` servers, Darwin indexes **`135` MCP tools** at boot while routing server `stderr` logs to `~/.darwin/mcp.log` to keep the TUI clean.

#### Configured MCP Servers ([`mcp.json`](mcp.json))

| Server Key | Package / Image | Launcher | Required Env / Notes | Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| `time` | `mcp-server-time` | `uvx` | None | Current time, timezone resolution, and conversion. |
| `sequential-thinking` | `@modelcontextprotocol/server-sequential-thinking` | `npx` | None | Dynamic thought scratchpad for structured multi-step planning and revision. |
| `filesystem` | `@modelcontextprotocol/server-filesystem` | `npx` | Scoped path arg in `mcp.json` | Scoped local file read/write, directory trees, and file metadata. |
| `sqlite` | `mcp-server-sqlite` | `uvx` | `--db-path darwin.db` | SQLite schema introspection (`list_tables`, `describe_table`) and SQL queries. |
| `postgres` | `@modelcontextprotocol/server-postgres` | `npx` | `POSTGRES_URL` arg | PostgreSQL schema inspection and read-only SQL queries. |
| `fetch` | `mcp-server-fetch` | `uvx` | None | Fast HTTP fetching and HTML-to-Markdown/text extraction. |
| `playwright` | `@playwright/mcp@latest` | `npx` | Chromium headless | Headless browser automation, DOM snapshots, screenshots, network/console inspection. |
| `firecrawl` | `firecrawl-mcp` | `npx` | `FIRECRAWL_API_KEY` | Deep web scraping, crawling, and clean Markdown extraction. |
| `exa` | `exa-mcp-server` | `npx` | `EXA_API_KEY` | Neural web search for technical and research queries. |
| `github` | `ghcr.io/github/github-mcp-server` | `docker run` | `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub repository browsing, code search, commits, issues, and pull requests. |
| `git` | `mcp-server-git` | `uvx` | `--repository .` | Local Git status, diffs (staged/unstaged), commit logs, branches, and commits. |
| `docker` | `mcp-server-docker` | `uvx` | Docker daemon running | Host container lifecycle management, logs, images, networks, and volumes. |
| `context7` | `@upstash/context7-mcp` | `npx` | Optional `CONTEXT7_API_KEY` | Real-time retrieval of versioned library documentation (`resolve-library-id`, `query-docs`). |

#### How Tool RAG Works ([`src/darwin/tools/registry.py`](src/darwin/tools/registry.py))

Binding `135` MCP tools on every LLM call bloats the prompt by 20,000+ tokens and degrades tool selection accuracy. Darwin solves this with a hybrid **Tool RAG** pipeline:
1. **Indexing at Boot:** Every connected MCP tool's `{name}: {description}` is embedded with `all-MiniLM-L6-v2` into Qdrant's `tools_registry` collection using deterministic SHA-1 point IDs.
2. **Per-Turn Hybrid Retrieval:** On each turn, `select_tools()` queries Qdrant for the top `TOOL_RAG_TOP_K` (default `12`) semantic matches against the user's latest prompt, and unions up to `4` additional tools whose names lexically match non-generic query tokens (e.g., matching `"repos"` to `github__search_repositories`).

### 5.3 Hardened Multi-Language Execution Sandbox

Defined in [`src/darwin/sandbox/`](src/darwin/sandbox/), Darwin's sandbox isolates untrusted or multi-language code from the host machine:

- **Zero Host Trust by Default:**
  - `--network none` (unless `network=True` is explicitly passed and approved)
  - `--read-only` root filesystem with `--tmpfs /tmp:rw,exec,size=512m` for temporary build artifacts and compiler caches (`GOCACHE`, `CARGO_HOME`, `npm_config_cache`, `BUN_INSTALL_CACHE_DIR`)
  - Workspace mounted read-only (`-v $WORKSPACE_ROOT:/workspace:ro`) unless `writable=True` is explicitly requested
  - `--cap-drop ALL` and `--security-opt no-new-privileges`
  - Runs as non-root host UID/GID (`--user $(id -u):$(id -g)`)
  - Strict cgroup limits: `--memory 1g`, `--cpus 1`, `--pids-limit 256`, and hard execution timeouts (kills and removes the container on timeout)
  - Host environment variables (and secrets) are **never** forwarded into sandbox containers.
- **Lima VM Fallback (`src/darwin/sandbox/lima.py`):** When `SANDBOX_BACKEND=lima` (or when Docker is unavailable), Darwin can execute commands inside a persistent `darwin-sandbox` Linux VM via `limactl`, mounting only `WORKSPACE_ROOT` at `/workspace`.

### 5.4 Security, Guardrails & Permission Model

Darwin enforces defense-in-depth across four layers in [`src/darwin/guardrails/`](src/darwin/guardrails/):

1. **Prompt Injection & Secret Redaction (`guard.py` & `redaction.py`):**
   - Rejects user inputs containing prompt-injection markers (`ignore previous instructions`, `ignore all prior`, `system prompt`, `you are now`, `do anything`).
   - Redacts API keys, Bearer tokens, AWS access keys (`AKIA...`), PEM private keys, JWTs, 16-digit card numbers, and email addresses into `[REDACTED]` across both inputs and outputs.
2. **Deterministic Banned Command Policy (`command_policy.py`):**
   - Rejects destructive shell patterns before execution in both `run_shell` and `sandbox`: recursive/forced `rm` (`rm -rf`), `mkfs`, fork bombs (`:(){ :|:& };:`), `shutdown`, `reboot`, and raw disk writes (`dd if=`).
3. **Granular Policy Rules & Workspace Scope (`permissions.py`, `scope.py`, `permissions.json`):**
   - Evaluates tool calls against [`permissions.json`](permissions.json) using `Tool(glob)` rules across `deny`, `ask`, and `allow` lists (`Read(...)`, `Write(...)`, `Bash(...)`, or exact tool names):
     - **`deny` always wins** and can never be overridden (e.g., `Read(~/.ssh/**)`, `Read(~/.aws/**)`, `Read(~/.config/gcloud/**)`, `Read(~/.darwin/**)`, `Bash(sudo rm*)`).
     - **`ask` rules** (e.g., `Bash(sudo *)`) and any file path resolving outside `WORKSPACE_ROOT` trigger a **Just-in-Time (JIT) Escalation Interrupt**, allowing you to grant access `[1] allow once`, `[2] allow for session`, or `[3] deny`.
4. **Two-Tier HITL Mutability Gate (`orchestrator.py`):**
   - **Tier 1 (Auto-Approved):** Read-only native tools (`read_file`, `list_directory`, `parse_document`, `sandbox_containers`, `email_read`, `memory_recall`, `memory_save`, `notify_user`) and MCP tools listed in `READ_ONLY_MCP_TOOLS`.
   - **Tier 2 (Human Approval Required):** All mutating native tools (`write_file`, `run_shell`, `email_send`, `run_sandboxed`, `run_code`, `sandbox_stop`) and any MCP tool not in `READ_ONLY_MCP_TOOLS` pause graph execution via `interrupt()` until explicitly approved (`y/n`).

### 5.5 Hybrid Tiered Memory Architecture

Darwin maintains context across three tiers:
1. **Short-Term Conversational Buffer (`orchestrator.py`):** Managed inside `AgentState["messages"]` via LangGraph's `add_messages` reducer and checkpointed to PostgreSQL. Automatically pruned to the most recent `50` messages (`MAX_BUFFER_MESSAGES`).
2. **Long-Term Vector Memory (`Qdrant` via `mem0`):** Stores semantic embeddings (`384` dims) of facts and preferences in the `memories` collection.
3. **Long-Term Knowledge Graph (`Neo4j` via `mem0`):** Extracts and persists structured entity-relationship triples alongside vector memories, recalled automatically before each turn and injected into the system context.

---

## 6. Terminal UI (TUI) & Diagnostic CLIs

### Interactive Slash Commands

When running `uv run darwin`, type `/` to open the autocompletion menu:

| Command | Action |
| :--- | :--- |
| `/new` | Start a fresh conversation session (named automatically from your next message). |
| `/sessions` | Open an interactive arrow-key (`↑`/`↓`) dialog to switch between saved PostgreSQL sessions. |
| `/session` | Print a formatted table of recent sessions, latest checkpoint IDs, and checkpoint counts. |
| `/session <id>` | Switch directly to a specific session ID (e.g., `/session git-status-repo`). |
| `/themes` | Open an interactive arrow-key (`↑`/`↓`) picker to switch TUI color themes live. |
| `/theme <name>` | Switch directly to a theme: `tokyo-night` (default), `dracula`, `catppuccin`, `nord`, or `gruvbox`. |
| `/exit` or `/quit` | Gracefully close MCP sessions and exit Darwin. |

### Standalone Diagnostic CLIs

You can test the MCP subsystem or the execution sandbox independently without launching the full agent loop:

```bash
# 1. Inspect & test MCP servers independently
uv run python -m darwin.mcp.check                                              # List all connected MCP tools
uv run python -m darwin.mcp.check time                                         # List tools from the 'time' server
uv run python -m darwin.mcp.check time get_current_time '{"timezone": "UTC"}'  # Call a specific MCP tool

# 2. Verify execution sandbox backends & language runners
uv run python -m darwin.sandbox.check                                          # Check Docker/Lima availability & image allowlist
uv run python -m darwin.sandbox.check python                                   # Run built-in test snippet in python:3.12-slim
uv run python -m darwin.sandbox.check rust 'fn main(){println!("hello")}'      # Run custom command/snippet in rust:1.82-slim
uv run python -m darwin.sandbox.check lima                                     # Test the opt-in Lima VM backend
```

---

## 7. Configuration Reference

All settings are read from `.env` via [`src/darwin/core/config.py`](src/darwin/core/config.py):

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DARWIN_LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL. |
| `DARWIN_LLM_API_KEY` | `""` | **Required.** API key for your LLM provider. |
| `DARWIN_LLM_MODEL` | `gpt-4o-mini` | Model identifier to use for reasoning and `mem0` fact extraction. |
| `DARWIN_THEME` | `tokyo-night` | Initial TUI color theme (`tokyo-night`, `dracula`, `catppuccin`, `nord`, `gruvbox`). |
| `POSTGRES_URL` | `postgresql://darwin:darwin@localhost:5432/darwin` | PostgreSQL connection string for `AsyncPostgresSaver` and session queries. |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant HTTP endpoint for `memories` and `tools_registry`. |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt/Aura URI for graph memory. |
| `NEO4J_USER` / `NEO4J_PASSWORD` | `neo4j` / `darwin123` | Neo4j authentication credentials. |
| `REDIS_URL` | `redis://localhost:6379/0` | Valkey/Redis URL for `RQ` background queues. |
| `WORKSPACE_ROOT` | Current working directory | Root directory the agent is allowed to read/write without scope escalation. |
| `PERMISSIONS_PATH` | `permissions.json` | Path to declarative `allow` / `ask` / `deny` permission rules. |
| `MCP_CONFIG_PATH` | `mcp.json` | Path to MCP server definitions. |
| `TOOL_RAG_ENABLED` | `true` | Enable Qdrant-backed per-turn MCP tool masking. |
| `TOOL_RAG_TOP_K` | `12` | Number of semantic tool matches retrieved from Qdrant per turn. |
| `READ_ONLY_MCP_TOOLS` | *(Comma-separated list)* | MCP tool names that bypass `y/n` HITL approval (Tier 1). |
| `SANDBOX_BACKEND` | `auto` | Execution sandbox backend (`auto`, `docker`, or `lima`). |
| `SANDBOX_MEMORY` / `SANDBOX_CPUS` | `1g` / `1` | Per-container memory and CPU limits for Docker sandbox runs. |
| `SANDBOX_PIDS_LIMIT` | `256` | Maximum process count inside a sandbox container (prevents fork bombs). |
| `SANDBOX_TIMEOUT` | `120` | Default sandbox execution timeout in seconds. |
| `SANDBOX_VM_NAME` | `darwin-sandbox` | Instance name for the opt-in Lima virtual machine. |

---

## 8. Repository Layout

```text
Darwin/
├── assets/
│   └── tui-preview.svg           # Vector preview of the Darwin TUI (tokyo-night theme)
├── .env.example                  # Documented environment variable template
├── docker-compose.yml            # Local service stack: PostgreSQL 16, Qdrant, Neo4j 5, Valkey 8
├── mcp.json                      # 13 stdio MCP server configurations (135 tools)
├── permissions.json              # Declarative allow / ask / deny security rules
├── pyproject.toml                # Project metadata, dependencies, and `darwin` CLI script entry
├── README.md                     # Project documentation & architecture reference
├── LICENSE                       # MIT License
└── src/darwin/
    ├── __init__.py               # Environment & telemetry/logging silencing on import
    ├── main.py                   # Async CLI entrypoint, session loop, MCP & checkpointer lifecycle
    ├── tui.py                    # Rich + prompt_toolkit TUI, themes, banners, pickers, approval prompts
    ├── sessions.py               # Postgres checkpoint inspection & first-message session slugifier
    ├── core/
    │   ├── config.py             # Centralized environment configuration loader
    │   ├── llm.py                # Model-agnostic ChatOpenAI client factory
    │   ├── memory_client.py      # Singleton mem0 client (Qdrant vector + Neo4j graph + local MiniLM)
    │   ├── notify.py             # macOS osascript desktop notifications with stderr fallback
    │   ├── orchestrator.py       # LangGraph StateGraph: guard, agent, permissions, approve, tools
    │   └── queue.py              # Valkey/Redis + RQ TaskQueue wrapper
    ├── guardrails/
    │   ├── command_policy.py     # Regex filter blocking destructive shell commands
    │   ├── guard.py              # Prompt injection detector & input/output sanitization hooks
    │   ├── permissions.py        # Rule engine evaluating permissions.json + workspace scope
    │   ├── redaction.py          # Regex PII, secret, key, JWT, and card number redactor
    │   ├── schemas.py            # Pydantic tool argument schemas with control-char validation
    │   └── scope.py              # SessionScope manager for persistent & ephemeral path grants
    ├── mcp/
    │   ├── adapters.py           # JSON Schema -> Pydantic model & LangChain StructuredTool bridge
    │   ├── check.py              # Standalone CLI (`python -m darwin.mcp.check`) for testing MCP servers
    │   └── client.py             # AsyncExitStack stdio MCP client manager
    ├── sandbox/
    │   ├── __init__.py           # Backend router (`auto` | `docker` | `lima`)
    │   ├── check.py              # Standalone CLI (`python -m darwin.sandbox.check`) for testing sandboxes
    │   ├── docker.py             # Hardened `docker run` wrapper & 8-language image allowlist
    │   └── lima.py               # Opt-in Lima VM lifecycle & command runner
    └── tools/
        ├── __init__.py           # Exports `ALL_TOOLS` (14 native tools)
        ├── documents.py          # `parse_document` via Microsoft MarkItDown
        ├── email.py              # `email_read` / `email_send` via stdlib IMAP4_SSL / SMTP + leak guard
        ├── filesystem.py         # `read_file`, `write_file`, `list_directory`
        ├── memory_tool.py        # `memory_recall`, `memory_save`
        ├── notify_user.py        # `notify_user` desktop alert tool
        ├── registry.py           # Qdrant `tools_registry` indexer & hybrid semantic/lexical selector
        ├── sandbox.py            # `run_sandboxed`, `run_code`, `sandbox_containers`, `sandbox_stop`
        └── shell.py              # `run_shell` with secret-scrubbed env & TTY-aware sudo handling
```

---

## 9. Implementation Roadmap & Status

- [x] **Phase 1 — Core Design & Reasoning Engine**
  - [x] Custom LangGraph `StateGraph` orchestrator (`guard` → `agent` → `permissions` → `approve` → `tools`)
  - [x] Model-agnostic OpenAI-compatible client (`ChatOpenAI`)
  - [x] Durable PostgreSQL checkpointing (`AsyncPostgresSaver`) & auto-slugified session management
  - [x] Unified `Qdrant` vector store + `Neo4j` graph memory via `mem0` with local `all-MiniLM-L6-v2` embeddings
  - [x] `Valkey` / `Redis` + `RQ` background task queue foundation
- [x] **Phase 2 — Native Tooling & Guardrails**
  - [x] Sandboxed host shell runner (`run_shell`) with secret-scrubbed environment and banned-command policy
  - [x] Workspace-scoped OS file tools (`read_file`, `write_file`, `list_directory`)
  - [x] Universal document ingestion (`parse_document` via `MarkItDown` for PDF, DOCX, XLSX)
  - [x] Secure `IMAP`/`SMTP` email tools (`email_read`, `email_send`) with outbound secret leak protection
  - [x] Native desktop notifications (`notify_user` via `osascript`)
  - [x] Deterministic input/output guardrails, prompt injection detection, and PII/token redaction
- [x] **Phase 3 — MCP Subsystem & Dynamic Routing**
  - [x] Custom `stdio` MCP client and dynamic JSON-Schema-to-Pydantic LangChain tool bridge
  - [x] 13 MCP servers configured (`135` tools across `time`, `sequential-thinking`, `filesystem`, `sqlite`, `postgres`, `fetch`, `playwright`, `firecrawl`, `exa`, `github`, `git`, `docker`, `context7`)
  - [x] Hybrid **Tool RAG** (`tools_registry` in Qdrant + lexical union) masking MCP tools per turn
  - [x] Two-Tier HITL approval (`y/n`) and `permissions.json` + JIT out-of-workspace escalation (`1/2/3`)
- [x] **Phase 4 — Execution, Sandboxing & DevOps**
  - [x] Hardened multi-language Docker sandbox (`bash`, `python`, `node`, `bun`, `go`, `rust`, `cpp`, `java`)
  - [x] Opt-in Lima VM sandbox fallback (`darwin.sandbox.lima`)
  - [x] Local Git (`mcp-server-git`), remote GitHub (`github-mcp-server`), and Docker (`mcp-server-docker`) MCP integrations
- [ ] **Phase 5 — Future Extensions**
  - [ ] **Self-Tooling Engine:** Runtime meta-tooling pipeline for synthesizing, sandbox-testing, and dynamically registering new Python tools on the fly
  - [ ] **Additional Workspace MCPs:** Slack (`@modelcontextprotocol/server-slack`) and Notion (`notion-mcp`) integrations
  - [ ] **SSE / HTTP MCP Transports:** Extending `MCPClient` beyond `stdio` to remote HTTP/SSE MCP endpoints

---

## 10. License & Author

- **Author:** **Ayushya Saxena** ([@The-Tourist-170](https://github.com/The-Tourist-170))
- **License:** Released under the [MIT License](LICENSE).

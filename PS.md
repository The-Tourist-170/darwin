# Project Specification: Darwin

## 1. Overview

- **Project Name:** Darwin
- **Description:** An autonomous, general-purpose agentic execution engine inspired by Claude Code and Hermes Agent. Darwin is designed to autonomously reason, navigate file systems, execute code across sandboxed environments, interface with external platforms via standard protocols, and self-correct across complex workflows.

## 2. Core Architecture

### 2.1 State & Graph Engine

- **Orchestrator:** Custom LangGraph StateGraph operating as a tool-calling reasoning loop.
- **Model Connectivity:** Model-agnostic integration layer configurable via custom Base URL, API Key, and Model Name (supporting providers such as OpenAI, DeepSeek, and local vLLM/Ollama endpoints).
- **State Persistence & Checkpointing:** PostgreSQL checkpointer (PostgresSaver) for durable state snapshots, allowing workflows to survive process reboots and support long-lived sessions.
- **Asynchronous Queue Management:** Redis/Valkey integrated with RQ (Redis Queue) to offload non-blocking background tasks and decoupled pipeline jobs.
- **Hybrid Tiered Memory Architecture:**
  - **Short-Term Memory:** Conversational buffer window and message-state reducers managed within the LangGraph state.
  - **Long-Term Vector Memory:** Qdrant vector database (dedicated collections) for semantic similarity search, past context retrieval, and episodic memory.
  - **Long-Term Graph Memory:** Neo4j knowledge graph for structured entity-relationship tracking and conceptual mapping.

### 2.2 Safety, Governance & Validation

- **Deterministic Guardrails:** Input and output interception middleware to sanitize prompts, detect prompt injections, block banned shell commands, and redact sensitive tokens/PII before model invocation.
- **Structured Outputs:** Pydantic schemas enforcing strict JSON parsing, tool argument validation, and rule adherence.

## 3. Tooling & MCP Subsystem

### 3.1 Context Saturation Mitigation

Loading 100+ tools simultaneously triggers prompt bloat (20,000+ tokens per turn) and induces tool selection confusion. Darwin implements a dual mitigation strategy:

1. **Tool RAG (Dynamic Tool Masking via Qdrant):** Tool schemas and docstrings are indexed directly into a dedicated tools_registry collection in Qdrant (preventing multi-database sprawl). The agent dynamically retrieves and binds only the top 5–8 most relevant tools per turn based on user intent.
2. **Two-Tier Permission Model (Read vs. Mutate):**
   - **Tier 1 (Auto-Approved / Read-Only):** File reads, directory listing, web search, reading messages, and docker inspect.
   - **Tier 2 (Human-in-the-Loop Required / Mutating):** Sensitive operations trigger a LangGraph interrupt(), halting execution until approved via confirmation prompts (send_email, send_whatsapp, git push, docker rm -f, rm -rf).

### 3.2 Execution, Sandboxing & DevOps

- **Sandboxed Execution:** Isolated Docker containers and Lima virtual machines for safely building and running multi-language environments (Bash, Python, Node.js, Bun, Go, Rust, C++, Java).
- **Container Management:** mcp-server-docker for managing container lifecycles, health checks, images, and networks.
- **Version Control:** mcp-server-git for local repository operations (commits, diffs, branch management) alongside GitHub/GitLab MCP servers for remote operations (pull requests, issues, CI/CD pipelines, and releases).
- **On-Demand Technical Documentation:** context7-mcp for real-time retrieval of up-to-date, versioned library documentation and language syntax.

## 4. Tool & MCP Categorization

### Category A: Off-the-Shelf MCP Servers (Configure & Consume)

Standardized, community-maintained MCP servers integrated over stdio/SSE:

- **Core Utilities & Reasoning:**
  - **mcp-server-time:** Timezone resolution, UTC synchronization, and relative date calculation.
  - **@modelcontextprotocol/server-sequential-thinking:** Dynamic thought scratchpad for multi-step planning, plan revision, and step verification.
- **Storage & Local Files:**
  - **@modelcontextprotocol/server-filesystem:** Controlled local directory read/write access (natively covering local markdown vaults such as Obsidian and Logseq).
  - **@modelcontextprotocol/server-postgres / @modelcontextprotocol/server-sqlite:** Database introspection and SQL query execution.
- **Web & Networking:**
  - **@modelcontextprotocol/server-fetch:** Fast HTTP GET/POST operations and HTML-to-text extraction without browser overhead.
  - **firecrawl-mcp / exa-mcp-server:** Neural web search and clean Markdown scraping with automated proxy and layout handling.
  - **@modelcontextprotocol/server-puppeteer (or Playwright MCP):** Scripted headless browser automation, form submission, and visual capture for JavaScript-heavy pages.
- **External Workspaces:**
  - **@modelcontextprotocol/server-slack:** Slack workspace reading, thread tracking, and messaging.
  - **notion-mcp:** Notion database querying, page creation, and block updates.
  - **@github/mcp-server:** Repository exploration, diff inspections, and issue/PR management.

### Category B: Custom Tools & Engine Logic (Built In-House)

Custom Python modules tightly coupled with the host runtime, safety guards, or checkpointer:

- **Sandboxed Shell Tool:** Python wrapper around subprocess.run with timeout controls, exit code verification, and output truncation.
- **Universal Document Ingestion Tool:** Local parsing engine utilizing Microsoft markitdown or IBM docling to convert PDFs, spreadsheets, and Word documents into Markdown.
- **Secure IMAP/SMTP Client:** Custom email handling module with explicit credential isolation and outbound leak protection.
- **Native HITL & Notification Engine (notify_user):** Integrated directly into the LangGraph state using interrupt() and local desktop notifications (osascript on macOS) to request human authorization.
- **Vector / Episodic Retrieval Tool:** Custom state-level retrieval mechanism interfacing with Qdrant collections for episodic memory and dynamic context retrieval.
- **Self-Tooling Engine:** Meta-tooling pipeline allowing the agent to write new Python code, execute it in a temporary test sandbox to verify syntax and behavior, and dynamically register it into the runtime tool registry.

## 5. Architectural Phases

```text
┌────────────────────────────────────────────────────────┐
│ Phase 1: Core Design & Reasoning Engine                │
│ • StateGraph orchestrator, model client, persistence   │
│ • Checkpointing (Postgres), queues (Valkey/RQ)         │
│ • Unified vector store (Qdrant) + graph memory (Neo4j) │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 2: Native Tooling                                │
│ • Sandboxed shell, OS file operations, document parser │
│ • Deterministic guardrails and Pydantic schemas        │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 3: MCP Subsystem & Dynamic Routing               │
│ • MCP client integration (Category A servers)          │
│ • Tool RAG dynamic masking via Qdrant & 2-tier HITL    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 4: Execution, Sandboxing & DevOps                │
│ • Docker/Lima multi-runtime sandbox                    │
│ • Git/GitHub MCP integration, container lifecycles     │
└────────────────────────────────────────────────────────┘
```

## 6. Implementation Sub-Phasing Roadmap for Tools & MCP (Ordered)

- **Sub-Phase 1: Foundation (OS & Local Disk)**
  - Integrate mcp-server-time.
  - Configure @modelcontextprotocol/server-filesystem.
  - Implement custom sandboxed shell runner.
- **Sub-Phase 2: Ingestion & Web Access**
  - Integrate @modelcontextprotocol/server-fetch.
  - Configure exa-mcp-server / firecrawl-mcp.
  - Build the custom markitdown / docling document parsing tool.
- **Sub-Phase 3: Persistence, Databases & HITL Safety**
  - Integrate database MCPs (server-postgres / server-sqlite).
  - Implement unified memory integration (Qdrant for vector/tool indexing + Neo4j for graph knowledge).
  - Wire LangGraph interrupt() gates for mutating operations.
- **Sub-Phase 4: Ecosystems & Workspaces**
  - Connect @github/mcp-server.
  - Integrate notion-mcp and Slack MCP.
  - Build the custom IMAP/SMTP email client.
- **Sub-Phase 5: Advanced Automation & Meta-Extension**
  - Integrate Playwright/Puppeteer MCP for dynamic browsing.
  - Build the self-tooling engine for runtime code synthesis and registration.

## 7. Engineering Guidelines

- **Unified Vector Store:** Standardize on Qdrant across all embedding and retrieval tasks (episodic memory and Tool RAG) using separate collection names (memories, tools_registry) to prevent infrastructure bloat.
- **Isolation of Concerns:** Develop and test each phase and sub-phase independently before integration.
- **Sequential Execution:** Implement one phase at a time; avoid premature optimization or partial implementations across multiple phases.
- **Simplicity & Clean Code:** Prioritize explicit, maintainable Python patterns over overly clever abstractions. Keep control flow transparent.
- **No Unnecessary Boilerplate:** Reject generated code bloat; retain only essential logic, explicit error handling, and direct interfaces.
- **Continuous Documentation:** Track all architectural decisions, breaking changes, test results, and implementation logs inside NOTES.md.
- Force the LLM to plan before executing.

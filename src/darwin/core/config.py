"""Central configuration for Darwin. All values come from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Model provider (any OpenAI-compatible endpoint: OpenAI, DeepSeek, vLLM, Ollama)
    LLM_BASE_URL: str = os.getenv("DARWIN_LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_API_KEY: str = os.getenv("DARWIN_LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("DARWIN_LLM_MODEL", "gpt-4o-mini")

    # Persistence & memory
    # Credentials default to the docker-compose services — zero config needed.
    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "postgresql://darwin:darwin@localhost:5432/darwin")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "darwin123")

    # Background queue
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # MCP subsystem
    MCP_CONFIG_PATH: str = os.getenv("MCP_CONFIG_PATH", "mcp.json")
    MCP_SERVER_COMMAND: str = os.getenv("MCP_SERVER_COMMAND", "")
    TOOL_RAG_ENABLED: bool = os.getenv("TOOL_RAG_ENABLED", "true").lower() == "true"
    TOOL_RAG_TOP_K: int = int(os.getenv("TOOL_RAG_TOP_K", "12"))
    # MCP tools that skip HITL approval (everything else is treated as mutating)
    READ_ONLY_MCP_TOOLS: list[str] = os.getenv(
        "READ_ONLY_MCP_TOOLS",
        "get_current_time,convert_time,fetch,"
        "read_file,read_text_file,read_multiple_files,list_directory,"
        "directory_tree,search_files,get_file_info,list_allowed_directories,"
        "list_tables,describe_table,"
        "browser_snapshot,browser_take_screenshot,browser_console_messages,"
        "browser_network_requests,browser_wait_for,"
        "get_file_contents,list_commits,get_commit,search_code,search_repositories,"
        "list_branches,list_issues,get_issue,list_issue_comments,list_pull_requests,"
        "get_pull_request,get_pull_request_files,get_pull_request_diff,"
        "get_pull_request_comments,get_pull_request_reviews,list_releases,get_latest_release,"
        "git_status,git_diff,git_diff_unstaged,git_diff_staged,git_log,git_show,"
        "list_containers,container_logs,inspect_container,list_images,list_networks,list_volumes,"
        "resolve-library-id,query-docs",
    ).split(",")

    # Permission boundary
    WORKSPACE_ROOT: str = os.getenv("WORKSPACE_ROOT", str(Path.cwd()))
    PERMISSIONS_PATH: str = os.getenv("PERMISSIONS_PATH", "permissions.json")

    # Sandbox (execution isolation; docker is the default backend)
    SANDBOX_BACKEND: str = os.getenv("SANDBOX_BACKEND", "auto")  # auto | docker | lima
    SANDBOX_MEMORY: str = os.getenv("SANDBOX_MEMORY", "1g")
    SANDBOX_CPUS: str = os.getenv("SANDBOX_CPUS", "1")
    SANDBOX_PIDS_LIMIT: int = int(os.getenv("SANDBOX_PIDS_LIMIT", "256"))
    SANDBOX_TIMEOUT: int = int(os.getenv("SANDBOX_TIMEOUT", "120"))
    SANDBOX_VM_NAME: str = os.getenv("SANDBOX_VM_NAME", "darwin-sandbox")

    # Email (optional; without credentials the email tools report disabled)
    EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    IMAP_HOST: str = os.getenv("IMAP_HOST", "")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))


config = Config()

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from contextlib import AsyncExitStack
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = None
    StdioServerParameters = None

AIRA_HOME = Path.home() / ".aira"
MCP_CONFIG = AIRA_HOME / "mcp_servers.json"

MCP_PRESETS = {
    "filesystem": {
        "command": "npx",
        "args": "-y @modelcontextprotocol/server-filesystem {dirs}",
        "description": "Read/write files and directories"
    },
    "github": {
        "command": "npx",
        "args": "-y @modelcontextprotocol/server-github",
        "description": "GitHub API integration (token in env)"
    },
    "playwright": {
        "command": "npx",
        "args": "-y @playwright/mcp",
        "description": "Browser automation with Playwright"
    },
    "sqlite": {
        "command": "npx",
        "args": "-y @modelcontextprotocol/server-sqlite {db}",
        "description": "SQLite database access"
    },
    "fetch": {
        "command": "npx",
        "args": "-y @anthropic/mcp-server-fetch",
        "description": "HTTP fetch and web scraping"
    },
    "memory": {
        "command": "npx",
        "args": "-y @modelcontextprotocol/server-memory",
        "description": "Knowledge graph memory"
    },
    "sequential-thinking": {
        "command": "npx",
        "args": "-y @modelcontextprotocol/server-sequential-thinking",
        "description": "Multi-step reasoning chains"
    },
    "brave-search": {
        "command": "npx",
        "args": "-y @anthropic/mcp-server-brave-search",
        "description": "Web search via Brave API"
    },
    "puppeteer": {
        "command": "npx",
        "args": "-y @anthropic/mcp-server-puppeteer",
        "description": "Browser automation (headless Chrome)"
    },
    "docker": {
        "command": "npx",
        "args": "-y @anthropic/mcp-server-docker",
        "description": "Docker container management"
    },
    "git": {
        "command": "npx",
        "args": "-y @anthropic/mcp-server-git",
        "description": "Git operations"
    },
}


def _load_servers() -> dict:
    if MCP_CONFIG.exists():
        try:
            return json.loads(MCP_CONFIG.read_text())
        except Exception:
            pass
    return {}


def _save_servers(servers: dict):
    AIRA_HOME.mkdir(exist_ok=True)
    MCP_CONFIG.write_text(json.dumps(servers, indent=2))


def mcp_list_servers() -> list[dict]:
    servers = _load_servers()
    return [{"name": k, **v} for k, v in servers.items()]


def mcp_add_server(name: str, command: str, args: str = "", env: dict | None = None) -> dict:
    servers = _load_servers()
    if name in servers:
        return {"success": False, "error": f"Server '{name}' already exists"}
    servers[name] = {"command": command, "args": args, "env": env or {}}
    _save_servers(servers)
    return {"success": True, "name": name}


def mcp_enable_preset(preset: str, params: str = "") -> dict:
    """Enable a well-known MCP server by preset name."""
    if preset not in MCP_PRESETS:
        return {"success": False, "error": f"Unknown preset '{preset}'", "presets": list(MCP_PRESETS.keys())}
    p = MCP_PRESETS[preset]
    args = p["args"]
    if "{dirs}" in args and params:
        args = args.replace("{dirs}", params)
    elif "{db}" in args and params:
        args = args.replace("{db}", params)
    return mcp_add_server(preset, p["command"], args)


def mcp_remove_server(name: str) -> dict:
    servers = _load_servers()
    if name not in servers:
        return {"success": False, "error": f"Server '{name}' not found"}
    del servers[name]
    _save_servers(servers)
    return {"success": True, "name": name}


def mcp_discover() -> list[dict]:
    """Scan common config files for existing MCP server configurations."""
    found = []
    search_paths = [
        Path.home() / ".claude" / "claude_desktop_config.json",
        Path.home() / ".codegpt" / "mcp.json",
        Path.home() / ".cursor" / "mcp.json",
        Path.home() / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "mcp_settings.json",
    ]
    for p in search_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                mcp_servers = data.get("mcpServers", data.get("servers", {}))
                for name, cfg in mcp_servers.items():
                    found.append({
                        "source": p.name,
                        "name": name,
                        "command": cfg.get("command", ""),
                        "args": " ".join(cfg.get("args", [])),
                    })
            except Exception:
                pass
    return found


async def _connect_and_list_tools(command: str, args_str: str):
    params = StdioServerParameters(command=command, args=args_str.split() if args_str else [])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in result.tools]


def mcp_list_tools(server_name: str) -> list[dict] | dict:
    import asyncio
    servers = _load_servers()
    if server_name not in servers:
        return {"success": False, "error": f"Server '{server_name}' not found"}
    srv = servers[server_name]
    try:
        tools = asyncio.run(_connect_and_list_tools(srv["command"], srv.get("args", "")))
        return {"success": True, "tools": tools}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _connect_and_call_tool(command: str, args_str: str, tool_name: str, tool_args: dict):
    params = StdioServerParameters(command=command, args=args_str.split() if args_str else [])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_args)
            return result.content if hasattr(result, 'content') else str(result)


def mcp_call_tool(server_name: str, tool_name: str, tool_args: dict | None = None) -> dict:
    import asyncio
    servers = _load_servers()
    if server_name not in servers:
        return {"success": False, "error": f"Server '{server_name}' not found"}
    srv = servers[server_name]
    try:
        result = asyncio.run(_connect_and_call_tool(srv["command"], srv.get("args", ""), tool_name, tool_args or {}))
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

"""
MCP (Model Context Protocol) Support for Dymo Code
Allows custom tool servers to extend the agent's capabilities
"""

import os
import json
import subprocess
import threading
import queue
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path

from .logger import log_error, log_debug
from .config import COLORS

# ═══════════════════════════════════════════════════════════════════════════════
# MCP Server Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MCPServerConfig:
    """Configuration for an MCP server"""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""

@dataclass
class MCPTool:
    """Represents a tool provided by an MCP server"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str

# ═══════════════════════════════════════════════════════════════════════════════
# MCP Server Connection
# ═══════════════════════════════════════════════════════════════════════════════

class MCPServerConnection:
    """Manages connection to a single MCP server"""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.tools: Dict[str, MCPTool] = {}
        self._read_queue: queue.Queue = queue.Queue()
        self._reader_thread: Optional[threading.Thread] = None
        self._request_id = 0

    def connect(self) -> bool:
        """Start the MCP server process"""
        try:
            env = os.environ.copy()
            env.update(self.config.env)

            self.process = subprocess.Popen(
                [self.config.command] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1
            )

            # Start reader thread
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()

            # Initialize connection
            self._send_initialize()

            # Get available tools
            self._get_tools()

            log_debug(f"Connected to MCP server: {self.config.name}")
            return True

        except Exception as e:
            log_error(f"Failed to connect to MCP server {self.config.name}", e)
            return False

    def disconnect(self):
        """Stop the MCP server process"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None

    def _read_output(self):
        """Read output from the MCP server"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    try:
                        response = json.loads(line)
                        self._read_queue.put(response)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                break

    def _send_request(self, method: str, params: Dict[str, Any] = None) -> Optional[Dict]:
        """Send a JSON-RPC request to the server"""
        if not self.process:
            return None

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method
        }
        if params:
            request["params"] = params

        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()

            # Wait for response
            try:
                response = self._read_queue.get(timeout=30)
                return response
            except queue.Empty:
                return None

        except Exception as e:
            log_error(f"MCP request failed: {method}", e)
            return None

    def _send_initialize(self):
        """Send initialize request"""
        response = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "dymo-code",
                "version": "1.0.0"
            }
        })

        if response and "result" in response:
            # Send initialized notification
            self._send_request("notifications/initialized")

    def _get_tools(self):
        """Get available tools from the server"""
        response = self._send_request("tools/list")

        if response and "result" in response:
            tools = response["result"].get("tools", [])
            for tool in tools:
                mcp_tool = MCPTool(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {}),
                    server_name=self.config.name
                )
                self.tools[tool["name"]] = mcp_tool

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on this server"""
        response = self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })

        if response:
            if "result" in response:
                content = response["result"].get("content", [])
                if content:
                    # Extract text from content blocks
                    texts = []
                    for block in content:
                        if block.get("type") == "text":
                            texts.append(block.get("text", ""))
                    return "\n".join(texts) if texts else str(content)
                return str(response["result"])
            elif "error" in response:
                return f"Error: {response['error'].get('message', 'Unknown error')}"

        return "No response from MCP server"


# ═══════════════════════════════════════════════════════════════════════════════
# MCP Manager
# ═══════════════════════════════════════════════════════════════════════════════

class MCPManager:
    """Manages multiple MCP server connections"""

    def __init__(self):
        self.servers: Dict[str, MCPServerConnection] = {}
        self.config_path = Path.home() / ".dymo-code" / "mcp.json"

    def load_config(self) -> List[MCPServerConfig]:
        """Load MCP configuration from file"""
        configs = []

        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)

                for name, server_config in data.get("mcpServers", {}).items():
                    configs.append(MCPServerConfig(
                        name=name,
                        command=server_config.get("command", ""),
                        args=server_config.get("args", []),
                        env=server_config.get("env", {}),
                        enabled=server_config.get("enabled", True),
                        description=server_config.get("description", "")
                    ))

            except Exception as e:
                log_error("Failed to load MCP config", e)

        return configs

    def save_config(self, configs: List[MCPServerConfig]):
        """Save MCP configuration to file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "mcpServers": {
                config.name: {
                    "command": config.command,
                    "args": config.args,
                    "env": config.env,
                    "enabled": config.enabled,
                    "description": config.description
                }
                for config in configs
            }
        }

        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def connect_all(self):
        """Connect to all configured MCP servers"""
        configs = self.load_config()

        for config in configs:
            if config.enabled:
                self.connect_server(config)

    def connect_server(self, config: MCPServerConfig) -> bool:
        """Connect to a specific MCP server"""
        if config.name in self.servers:
            return True

        connection = MCPServerConnection(config)
        if connection.connect():
            self.servers[config.name] = connection
            return True
        return False

    def disconnect_all(self):
        """Disconnect from all MCP servers"""
        for connection in self.servers.values():
            connection.disconnect()
        self.servers.clear()

    def disconnect_server(self, name: str):
        """Disconnect from a specific server"""
        if name in self.servers:
            self.servers[name].disconnect()
            del self.servers[name]

    def get_all_tools(self) -> List[MCPTool]:
        """Get all tools from all connected servers"""
        tools = []
        for connection in self.servers.values():
            tools.extend(connection.tools.values())
        return tools

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions in OpenAI format for API calls"""
        definitions = []

        for tool in self.get_all_tools():
            definitions.append({
                "type": "function",
                "function": {
                    "name": f"mcp_{tool.server_name}_{tool.name}",
                    "description": f"[MCP:{tool.server_name}] {tool.description}",
                    "parameters": tool.input_schema
                }
            })

        return definitions

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call an MCP tool by name"""
        # Parse the tool name to find server and actual tool name
        # Format: mcp_servername_toolname
        if tool_name.startswith("mcp_"):
            parts = tool_name[4:].split("_", 1)
            if len(parts) == 2:
                server_name, actual_tool = parts

                if server_name in self.servers:
                    connection = self.servers[server_name]
                    if actual_tool in connection.tools:
                        return connection.call_tool(actual_tool, arguments)

        return f"MCP tool not found: {tool_name}"

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool name is an MCP tool"""
        return tool_name.startswith("mcp_")

    def add_server(self, name: str, command: str, args: List[str] = None,
                   env: Dict[str, str] = None, description: str = "") -> bool:
        """Add a new MCP server configuration"""
        config = MCPServerConfig(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
            enabled=True,
            description=description
        )

        # Save to config
        configs = self.load_config()
        configs = [c for c in configs if c.name != name]  # Remove existing
        configs.append(config)
        self.save_config(configs)

        # Try to connect
        return self.connect_server(config)

    def remove_server(self, name: str):
        """Remove an MCP server configuration"""
        self.disconnect_server(name)

        configs = self.load_config()
        configs = [c for c in configs if c.name != name]
        self.save_config(configs)

    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all configured servers"""
        configs = self.load_config()
        status = {}

        for config in configs:
            is_connected = config.name in self.servers
            tool_count = len(self.servers[config.name].tools) if is_connected else 0

            status[config.name] = {
                "enabled": config.enabled,
                "connected": is_connected,
                "command": config.command,
                "tool_count": tool_count,
                "description": config.description
            }

        return status


# ═══════════════════════════════════════════════════════════════════════════════
# Global MCP Manager Instance
# ═══════════════════════════════════════════════════════════════════════════════

mcp_manager = MCPManager()


def get_mcp_tool_definitions() -> List[Dict[str, Any]]:
    """Get tool definitions from all connected MCP servers"""
    return mcp_manager.get_tool_definitions()


def execute_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Execute an MCP tool"""
    return mcp_manager.call_tool(tool_name, arguments)


def is_mcp_tool(tool_name: str) -> bool:
    """Check if a tool is an MCP tool"""
    return mcp_manager.is_mcp_tool(tool_name)

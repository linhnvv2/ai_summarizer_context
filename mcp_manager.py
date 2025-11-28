import asyncio
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import threading

import logging

class MCPManager:
    """
    Quản lý kết nối MCP servers (stdio) và gọi tools/resources.
    """
    def __init__(self, servers_cfg: List[Dict[str, Any]]):
        self.servers_cfg = servers_cfg
        self.exit_stack = AsyncExitStack()
        self.sessions: Dict[str, ClientSession] = {}
        self.loop = asyncio.new_event_loop()
        self._thread = None

    def start(self):
        logging.info("Starting MCPManager...")
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect_all())

    async def _connect_all(self):
        for s in self.servers_cfg:
            try:
                logging.info(f"[MCP] Connecting to {s['name']}...")
                params = StdioServerParameters(
                    command=s["command"],
                    args=s.get("args", []),
                    env=s.get("env", None)
                )
                transport = await self.exit_stack.enter_async_context(stdio_client(params))
                stdio, write = transport
                session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
                await session.initialize()
                self.sessions[s["name"]] = session
                tools_resp = await session.list_tools()
                tool_names = [t.name for t in tools_resp.tools]
                logging.info(f"[MCP] Connected {s['name']} with tools: {tool_names}")
                print(f"[MCP] Connected {s['name']} with tools: {tool_names}")
            except Exception as e:
                logging.error(f"[MCP] Failed to connect {s.get('name')}: {e}", exc_info=True)
                print(f"[MCP] Failed to connect {s.get('name')}: {e}")

    def list_tools(self, server_name: str) -> List[str]:
        sess = self.sessions.get(server_name)
        if not sess: return []
        try:
            fut = asyncio.run_coroutine_threadsafe(sess.list_tools(), self.loop)
            resp = fut.result(timeout=5)
            return [t.name for t in resp.tools]
        except Exception as e:
            logging.error(f"[MCP] Error listing tools for {server_name}: {e}", exc_info=True)
            return []

    def call_tool(self, server_name: str, tool_name: str, args: Dict[str, Any]) -> Any:
        sess = self.sessions.get(server_name)
        if not sess:
            raise RuntimeError(f"MCP server {server_name} not connected")
        
        logging.info(f"[MCP] Calling tool {server_name}/{tool_name} with args: {args}")
        async def _call():
            return await sess.call_tool(tool_name, args)
        
        try:
            fut = asyncio.run_coroutine_threadsafe(_call(), self.loop)
            result = fut.result(timeout=60)
            logging.info(f"[MCP] Tool execution successful: {result}")
            return result
        except Exception as e:
            logging.error(f"[MCP] Tool execution failed: {e}", exc_info=True)
            raise

    def shutdown(self):
        async def _shutdown():
            await self.exit_stack.aclose()
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_shutdown(), self.loop).result(timeout=5)
            self.loop.call_soon_threadsafe(self.loop.stop)

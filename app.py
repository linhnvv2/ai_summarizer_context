# app.py
import sys, json, time
from pathlib import Path
from typing import Optional, Dict, Any, List
import threading

from PySide6 import QtWidgets, QtGui, QtCore
from pynput import mouse, keyboard
import win32clipboard as wcb
import win32con
import requests

# MCP (optional, enabled via config)
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CONFIG_PATH = Path("config.json")

DEFAULT_CONFIG = {
    "provider": "ollama",   # "ollama" | "lmstudio"
    "ollama": {
        "endpoint": "http://127.0.0.1:11434",
        "model": "gemma:2b",
        "temperature": 0.2,
        "max_tokens": 1024
    },
    "lmstudio": {
        "endpoint": "http://127.0.0.1:1234/v1",
        "model": "Meta-Llama-3.1-8B-Instruct-Q4_K_M",
        "temperature": 0.2,
        "max_tokens": 1024
    },
    "ui": {
        "summary_language": "vi",  # "vi" or "en"
        "trigger": {"modifier": "shift", "button": "right"},
        "hotkey": "<alt>+q"
    },
    "mcp": {
        "enabled": True,
        "servers": [
            {
                "name": "filesystem",
                "command": "npx",
                "args": ["@modelcontextprotocol/server-filesystem"],
                "env": {"ROOT_PATH": "C:/Users/YourUser/Documents"}
            }
        ]
    }
}

# -------- Providers ----------

class ProviderBase:
    def summarize(self, text: str, cfg: Dict[str, Any]) -> str:
        raise NotImplementedError()

class OllamaProvider(ProviderBase):
    def summarize(self, text: str, cfg: Dict[str, Any]) -> str:
        endpoint = cfg["endpoint"].rstrip("/")
        model = cfg["model"]
        temperature = cfg.get("temperature", 0.2)
        max_tokens = cfg.get("max_tokens", 1024)
        lang = cfg.get("summary_language", "vi")
        if lang == "vi":
            sys_prompt = (
                "Bạn là trợ lý tóm tắt. Hãy tóm tắt ngắn gọn bằng tiếng Việt, "
                "ưu tiên bullet points, giữ từ khóa quan trọng, nêu hành động chính."
            )
        else:
            sys_prompt = (
                "You are a summarization assistant. Summarize concisely in English, "
                "prefer bullet points, preserve key terms and main actions."
            )
        prompt = f"{sys_prompt}\n\nNội dung cần tóm tắt:\n{text}\n\nTóm tắt:"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        url = f"{endpoint}/api/generate"
        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data.get("response", "").strip()

class LMStudioProvider(ProviderBase):
    def summarize(self, text: str, cfg: Dict[str, Any]) -> str:
        base = cfg["endpoint"].rstrip("/")
        model = cfg["model"]
        temperature = cfg.get("temperature", 0.2)
        max_tokens = cfg.get("max_tokens", 1024)
        lang = cfg.get("summary_language", "vi")
        if lang == "vi":
            sys_prompt = (
                "Bạn là trợ lý tóm tắt. Tóm tắt ngắn gọn bằng tiếng Việt, "
                "dùng bullet points, giữ từ khóa và điểm chính."
            )
        else:
            sys_prompt = (
                "You are a summarization assistant. Summarize concisely in English, "
                "use bullet points, preserve key terms and key points."
            )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": text}
        ]
        url = f"{base}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return json.dumps(data, ensure_ascii=False)

# -------- Utilities ----------

def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    return DEFAULT_CONFIG

def save_config(cfg: Dict[str, Any]):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

def get_clipboard_text() -> Optional[str]:
    try:
        wcb.OpenClipboard()
        if wcb.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            data = wcb.GetClipboardData(win32con.CF_UNICODETEXT)
            return data
    except Exception:
        return None
    finally:
        try: wcb.CloseClipboard()
        except Exception: pass
    return None

# -------- Input Listener & Smart Copy ----------

class InputListener(QtCore.QObject):
    trigger = QtCore.Signal()  # Signal emitted when trigger combination is detected

    def __init__(self, cfg: Dict[str, Any]):
        super().__init__()
        self.cfg = cfg
        self.pressed_mod = {"shift": False, "ctrl": False, "alt": False}
        self.running = True

    def start(self):
        # Run listeners in a non-blocking way
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        
        # Hotkey listener
        hk_str = self.cfg.get("ui", {}).get("hotkey", "<alt>+q")
        self.hotkey_listener = keyboard.GlobalHotKeys({
            hk_str: self.on_hotkey
        })

        self.keyboard_listener.start()
        self.mouse_listener.start()
        self.hotkey_listener.start()

    def stop(self):
        if hasattr(self, 'keyboard_listener'): self.keyboard_listener.stop()
        if hasattr(self, 'mouse_listener'): self.mouse_listener.stop()
        if hasattr(self, 'hotkey_listener'): self.hotkey_listener.stop()

    def on_hotkey(self):
        self.trigger.emit()

    def on_press(self, key):
        if key == keyboard.Key.shift: self.pressed_mod["shift"] = True
        if key == keyboard.Key.ctrl: self.pressed_mod["ctrl"] = True
        if key == keyboard.Key.alt: self.pressed_mod["alt"] = True

    def on_release(self, key):
        if key == keyboard.Key.shift: self.pressed_mod["shift"] = False
        if key == keyboard.Key.ctrl: self.pressed_mod["ctrl"] = False
        if key == keyboard.Key.alt: self.pressed_mod["alt"] = False

    def on_click(self, x, y, button, pressed):
        if not pressed: return
        
        trigger_cfg = self.cfg.get("ui", {}).get("trigger", {})
        target_mod = trigger_cfg.get("modifier", "shift")
        target_btn = trigger_cfg.get("button", "right")
        
        is_right = (button == mouse.Button.right)
        is_mod_ok = self.pressed_mod.get(target_mod, False)

        # Check condition
        if target_btn == "right" and is_right and is_mod_ok:
            self.trigger.emit()

def simulate_ctrl_c():
    kb = keyboard.Controller()
    # Release modifiers that might be held down by the user (Shift, Alt, Ctrl)
    # This fixes the issue where Shift+RightClick makes the system see Shift+Ctrl+C
    with kb.pressed(keyboard.Key.ctrl):
        # Ensure Shift/Alt are NOT pressed during the copy command
        # Note: We can't easily 'block' physical keys, but we can try to release them logically.
        # A robust way is to release them, press C, then restore? 
        # Actually, just releasing them is usually enough.
        kb.release(keyboard.Key.shift)
        kb.release(keyboard.Key.alt)
        
        kb.press('c')
        kb.release('c')

def simulate_double_click():
    ms = mouse.Controller()
    ms.click(mouse.Button.left, 2)


# -------- Floating Panel (quick actions) ----------

class PopupPanel(QtWidgets.QWidget):
    resultReady = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(8,8,8,8)

        self.btnSummary = QtWidgets.QPushButton("📝 Tóm tắt")
        self.btnExplain = QtWidgets.QPushButton("🤔 Giải thích")
        self.btnTranslate = QtWidgets.QPushButton("🌐 Dịch (vi↔en)")
        self.btnCustom = QtWidgets.QPushButton("⚙️ Prompt tùy biến")

        for b in (self.btnSummary, self.btnExplain, self.btnTranslate, self.btnCustom):
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            self.layout().addWidget(b)

        self.textOriginal = ""
        self.callback = None

    def show_at_cursor(self, pos: QtCore.QPoint, text: str, callback):
        self.textOriginal = text
        self.callback = callback
        self.move(pos)
        self.show()

        # Kết nối signals (đơn giản hoá)
        self.btnSummary.clicked.connect(lambda: self._do("summary"))
        self.btnExplain.clicked.connect(lambda: self._do("explain"))
        self.btnTranslate.clicked.connect(lambda: self._do("translate"))
        self.btnCustom.clicked.connect(lambda: self._do("custom"))

    def _do(self, action: str):
        self.hide()
        if self.callback:
            self.callback(action, self.textOriginal)

# -------- MCP Manager ----------

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
        import threading
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect_all())

    async def _connect_all(self):
        for s in self.servers_cfg:
            try:
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
                print(f"[MCP] Connected {s['name']} with tools: {tool_names}")
            except Exception as e:
                print(f"[MCP] Failed to connect {s.get('name')}: {e}")

    def list_tools(self, server_name: str) -> List[str]:
        sess = self.sessions.get(server_name)
        if not sess: return []
        fut = asyncio.run_coroutine_threadsafe(sess.list_tools(), self.loop)
        resp = fut.result(timeout=5)
        return [t.name for t in resp.tools]

    def call_tool(self, server_name: str, tool_name: str, args: Dict[str, Any]) -> Any:
        sess = self.sessions.get(server_name)
        if not sess:
            raise RuntimeError(f"MCP server {server_name} not connected")
        async def _call():
            return await sess.call_tool(tool_name, args)
        fut = asyncio.run_coroutine_threadsafe(_call(), self.loop)
        return fut.result(timeout=60)

    def shutdown(self):
        async def _shutdown():
            await self.exit_stack.aclose()
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_shutdown(), self.loop).result(timeout=5)
            self.loop.call_soon_threadsafe(self.loop.stop)

# -------- MCP Panel ----------

class MCPPanel(QtWidgets.QDialog):
    def __init__(self, mcp_manager: MCPManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MCP – Chọn server & tool")
        self.resize(720, 520)
        self.mcp = mcp_manager
        self.extra_context = ""

        lay = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout(); lay.addLayout(top)
        self.cmbServer = QtWidgets.QComboBox(); self.btnRefresh = QtWidgets.QPushButton("Làm mới")
        top.addWidget(QtWidgets.QLabel("Server:")); top.addWidget(self.cmbServer, 1); top.addWidget(self.btnRefresh)

        mid = QtWidgets.QSplitter(); mid.setOrientation(QtCore.Qt.Horizontal); lay.addWidget(mid, 1)
        left = QtWidgets.QWidget(); leftLay = QtWidgets.QVBoxLayout(left)
        self.lstTools = QtWidgets.QListWidget(); self.txtToolDesc = QtWidgets.QPlainTextEdit(); self.txtToolDesc.setReadOnly(True)
        leftLay.addWidget(QtWidgets.QLabel("Tools:")); leftLay.addWidget(self.lstTools, 2)
        leftLay.addWidget(QtWidgets.QLabel("Mô tả tool:")); leftLay.addWidget(self.txtToolDesc, 1)
        right = QtWidgets.QWidget(); rightLay = QtWidgets.QVBoxLayout(right)
        self.txtArgs = QtWidgets.QPlainTextEdit(); self.txtArgs.setPlaceholderText('Nhập đối số JSON, ví dụ: {"path": "C:/tmp/readme.txt"}')
        self.btnRun = QtWidgets.QPushButton("▶ Chạy tool"); self.chkUseContext = QtWidgets.QCheckBox("Dùng kết quả làm ngữ cảnh tóm tắt")
        self.txtResult = QtWidgets.QPlainTextEdit(); self.txtResult.setReadOnly(True)
        rightLay.addWidget(QtWidgets.QLabel("Args (JSON):")); rightLay.addWidget(self.txtArgs, 2)
        rowBtns = QtWidgets.QHBoxLayout(); rowBtns.addWidget(self.btnRun); rowBtns.addStretch(1); rowBtns.addWidget(self.chkUseContext)
        rightLay.addLayout(rowBtns); rightLay.addWidget(QtWidgets.QLabel("Kết quả:")); rightLay.addWidget(self.txtResult, 2)
        mid.addWidget(left); mid.addWidget(right); mid.setSizes([320, 400])
        btns = QtWidgets.QHBoxLayout(); self.btnClose = QtWidgets.QPushButton("Đóng"); btns.addStretch(1); btns.addWidget(self.btnClose); lay.addLayout(btns)

        self.btnRefresh.clicked.connect(self._reload_servers)
        self.cmbServer.currentIndexChanged.connect(self._load_tools_for_server)
        self.lstTools.currentItemChanged.connect(self._on_tool_selected)
        self.btnRun.clicked.connect(self._run_selected_tool)
        self.btnClose.clicked.connect(self.accept)

        self._reload_servers()

    def _reload_servers(self):
        self.cmbServer.clear()
        if not self.mcp or not self.mcp.sessions:
            self.cmbServer.addItem("(chưa có server)")
            self.cmbServer.setEnabled(False)
            self.lstTools.clear(); self.txtToolDesc.setPlainText("")
            return
        self.cmbServer.setEnabled(True)
        for name in self.mcp.sessions.keys():
            self.cmbServer.addItem(name)
        self._load_tools_for_server()

    def _load_tools_for_server(self):
        self.lstTools.clear()
        server = self.cmbServer.currentText()
        if not server or server == "(chưa có server)":
            return
        try:
            tools = self.mcp.list_tools(server)
            for t in tools:
                self.lstTools.addItem(t)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "MCP", f"Lỗi lấy tools: {e}")

    def _on_tool_selected(self, cur: QtWidgets.QListWidgetItem, prev):
        server = self.cmbServer.currentText(); name = cur.text() if cur else ""
        self.txtToolDesc.setPlainText(f"Server: {server}\nTool: {name}\n\nNhập args JSON và bấm 'Chạy tool'.")
        if name.lower() in ("read_file", "fs.read_file", "file.read"):
            self.txtArgs.setPlainText('{"path": "C:/Users/YourUser/Documents/readme.txt"}')
        elif name.lower() in ("write_file", "fs.write_file"):
            self.txtArgs.setPlainText('{"path": "C:/tmp/out.txt", "content": "Xin chào MCP!"}')
        else:
            self.txtArgs.setPlainText("{}")

    def _run_selected_tool(self):
        server = self.cmbServer.currentText(); item = self.lstTools.currentItem()
        if not server or not item:
            QtWidgets.QMessageBox.information(self, "MCP", "Chọn server và tool trước.")
            return
        tool = item.text()
        try:
            args = json.loads(self.txtArgs.toPlainText() or "{}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "JSON lỗi", f"Không parse được args JSON: {e}")
            return
        try:
            out = self.mcp.call_tool(server, tool, args)
            if isinstance(out, (dict, list)):
                pretty = json.dumps(out, ensure_ascii=False, indent=2)
            else:
                pretty = str(out)
            self.txtResult.setPlainText(pretty)
            if self.chkUseContext.isChecked():
                self.extra_context = f"[MCP:{server}/{tool}]\n{pretty}"
            else:
                self.extra_context = ""
        except Exception as e:
            self.txtResult.setPlainText(f"❌ Lỗi chạy tool: {e}")
            self.extra_context = ""

# -------- Tray App ----------

class TrayApp(QtWidgets.QSystemTrayIcon):
    show_popup_signal = QtCore.Signal(str)

    def __init__(self, app: QtWidgets.QApplication):
        icon = app.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        super().__init__(icon)
        self.app = app
        self.menu = QtWidgets.QMenu()
        self.cfg = load_config()

        self.popup = PopupPanel()
        self.provider = self._make_provider()

        actProvO = self.menu.addAction("Provider: Ollama")
        actProvL = self.menu.addAction("Provider: LM Studio")
        self.menu.addSeparator()
        actMcpPanel = self.menu.addAction("MCP: Panel chọn server/tool")
        actMcpTools = self.menu.addAction("MCP: Liệt kê tools")
        self.menu.addSeparator()
        actCfg = self.menu.addAction("Cấu hình…")
        actQuit = self.menu.addAction("Thoát")

        actProvO.triggered.connect(lambda: self._set_provider("ollama"))
        actProvL.triggered.connect(lambda: self._set_provider("lmstudio"))
        actCfg.triggered.connect(self._open_config_dialog)
        actQuit.triggered.connect(lambda: self.app.quit())
        actMcpPanel.triggered.connect(self._open_mcp_panel)
        actMcpTools.triggered.connect(self._show_mcp_tools)

        self.setContextMenu(self.menu)
        self.setToolTip("AI Summarizer (Shift + Right Click để tóm tắt)")
        self.show()

        # MCP init
        self.mcp: Optional[MCPManager] = None
        if self.cfg.get("mcp", {}).get("enabled"):
            self.mcp = MCPManager(self.cfg["mcp"].get("servers", []))
            self.mcp.start()
        self.mcp_context = ""

        # Start Input Listener
        self.input_listener = InputListener(self.cfg)
        self.input_listener.trigger.connect(self._on_trigger)
        self.input_listener.start()
        
        self.show_popup_signal.connect(self._show_popup_safe)
        self.app.aboutToQuit.connect(self._on_exit)

    def _on_exit(self):
        if self.input_listener:
            self.input_listener.stop()

    def _set_provider(self, name: str):
        self.cfg["provider"] = name
        save_config(self.cfg)
        self.provider = self._make_provider()

    def _make_provider(self) -> ProviderBase:
        if self.cfg["provider"] == "lmstudio":
            return LMStudioProvider()
        return OllamaProvider()

    def _on_trigger(self):
        """
        Called when Shift+RightClick is detected.
        Executes 'Smart Copy':
        1. Try Ctrl+C
        2. If empty, Double Click -> Ctrl+C
        3. Show popup if text found
        """
        # Run in a separate thread or use QTimer to avoid blocking the signal?
        # Since we need to sleep/wait, using a QTimer sequence or a background worker is better.
        # But for simplicity, we can use a small delay loop here, BUT we must be careful not to freeze UI too long.
        # Better: Use a separate thread for the copy sequence to keep UI responsive.
        threading.Thread(target=self._smart_copy_sequence, daemon=True).start()

    def _smart_copy_sequence(self):
        # 1. Clear clipboard to detect new copy
        try:
            wcb.OpenClipboard()
            wcb.EmptyClipboard()
            wcb.CloseClipboard()
        except: pass

        # 2. First attempt: Ctrl+C (for existing selection)
        simulate_ctrl_c()
        text = self._wait_for_clipboard(timeout=0.2)

        # 3. If no text, try Auto-Select (Double Click)
        if not text:
            # We need to click where the mouse IS. 
            # Note: The user just Right-Clicked. The cursor is there.
            # We might need to close the context menu that just appeared from Right Click?
            # Shift+RightClick usually opens a context menu.
            # Sending Esc might close it, or clicking might close it.
            # Let's try Double Click directly.
            simulate_double_click()
            time.sleep(0.1) # Wait for selection animation
            simulate_ctrl_c()
            text = self._wait_for_clipboard(timeout=0.2)

        if text and text.strip():
            # Show popup on main thread
            self.show_popup_signal.emit(text)

    @QtCore.Slot(str)
    def _show_popup_safe(self, text):
        pos = QtGui.QCursor.pos()
        self.popup.show_at_cursor(pos, text, self._handle_action)

    def _wait_for_clipboard(self, timeout=0.5) -> Optional[str]:
        start = time.time()
        while time.time() - start < timeout:
            txt = get_clipboard_text()
            if txt and txt.strip():
                return txt
            time.sleep(0.05)
        return None

    def _handle_action(self, action: str, text: str):
        # Bơm ngữ cảnh MCP nếu có
        if self.mcp_context:
            text = (text + "\n\n---\nNgữ cảnh MCP:\n" + self.mcp_context).strip()
            self.mcp_context = ""

        cfg = self.cfg[self.cfg["provider"]].copy()
        cfg["summary_language"] = self.cfg["ui"].get("summary_language", "vi")

        if action == "summary":
            result = self._call_provider(lambda: self.provider.summarize(text, cfg))
        elif action == "explain":
            t2 = f"Hãy giải thích dễ hiểu (tiếng Việt, ngắn gọn, ví dụ thực tế):\n\n{text}" if cfg["summary_language"] == "vi" else f"Explain simply (English, concise, practical examples):\n\n{text}"
            result = self._call_provider(lambda: self.provider.summarize(t2, cfg))
        elif action == "translate":
            t2 = f"Dịch nội dung sau sang tiếng Việt, giữ thuật ngữ:\n\n{text}" if cfg["summary_language"] == "vi" else f"Translate the following to English, preserve terms:\n\n{text}"
            result = self._call_provider(lambda: self.provider.summarize(t2, cfg))
        else:
            prompt, ok = QtWidgets.QInputDialog.getMultiLineText(None, "Prompt tùy biến", "Nhập prompt (ứng dụng sẽ chèn nội dung đã chọn phía dưới):", "Hãy tóm tắt ngắn gọn, dùng bullet, giữ từ khóa…")
            if not ok: return
            t2 = f"{prompt.strip()}\n\nNội dung:\n{text}"
            result = self._call_provider(lambda: self.provider.summarize(t2, cfg))

        self._show_result(result)
        self._copy_to_clipboard(result)

    def _call_provider(self, fn):
        try:
            return fn()
        except Exception as e:
            return f"❌ Lỗi gọi model: {e}"

    def _show_result(self, content: str):
        w = QtWidgets.QDialog(); w.setWindowTitle("Kết quả AI")
        lay = QtWidgets.QVBoxLayout(w)
        txt = QtWidgets.QPlainTextEdit(); txt.setPlainText(content); lay.addWidget(txt)
        btns = QtWidgets.QHBoxLayout(); btnCopy = QtWidgets.QPushButton("Copy"); btnSave = QtWidgets.QPushButton("Lưu…"); btnClose = QtWidgets.QPushButton("Đóng")
        btns.addWidget(btnCopy); btns.addWidget(btnSave); btns.addWidget(btnClose); lay.addLayout(btns)
        btnCopy.clicked.connect(lambda: self._copy_to_clipboard(txt.toPlainText()))
        def save_file():
            path, _ = QtWidgets.QFileDialog.getSaveFileName(w, "Lưu kết quả", "summary.txt", "Text (*.txt)")
            if path: Path(path).write_text(txt.toPlainText(), encoding="utf-8")
        btnSave.clicked.connect(save_file); btnClose.clicked.connect(w.accept)
        w.resize(640, 420); w.exec()

    def _copy_to_clipboard(self, text: str):
        cb = QtWidgets.QApplication.clipboard(); cb.setText(text)

    def _open_mcp_panel(self):
        if not self.mcp:
            QtWidgets.QMessageBox.warning(None, "MCP", "MCP chưa bật hoặc chưa có server.")
            return
        dlg = MCPPanel(self.mcp)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.mcp_context = dlg.extra_context or ""

    def _show_mcp_tools(self):
        if not self.mcp:
            QtWidgets.QMessageBox.warning(None, "MCP", "MCP chưa bật")
            return
        items = []
        for name in self.mcp.sessions.keys():
            tools = self.mcp.list_tools(name)
            items.append(f"{name}: {', '.join(tools)}")
        QtWidgets.QMessageBox.information(None, "MCP Tools", "\n".join(items) or "Không có tool")

    def _open_config_dialog(self):
        w = QtWidgets.QDialog(); w.setWindowTitle("Cấu hình")
        lay = QtWidgets.QVBoxLayout(w)
        txt = QtWidgets.QPlainTextEdit(); txt.setPlainText(json.dumps(self.cfg, ensure_ascii=False, indent=2)); lay.addWidget(txt)
        btns = QtWidgets.QHBoxLayout(); btnSave = QtWidgets.QPushButton("Lưu"); btnCancel = QtWidgets.QPushButton("Huỷ")
        btns.addWidget(btnSave); btns.addWidget(btnCancel); lay.addLayout(btns)
        btnSave.clicked.connect(lambda: self._save_cfg_from_text(txt.toPlainText(), w))
        btnCancel.clicked.connect(w.reject)
        w.resize(720, 560); w.exec()

    def _save_cfg_from_text(self, content: str, dlg: QtWidgets.QDialog):
        try:
            cfg = json.loads(content)
            save_config(cfg); self.cfg = cfg; dlg.accept()
        except Exception as e:
            QtWidgets.QMessageBox.warning(dlg, "JSON lỗi", f"Không parse được config: {e}")

# -------- main ----------
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    tray = TrayApp(app)
    sys.exit(app.exec())

# chat_window.py
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from PySide6 import QtWidgets, QtGui, QtCore

class ChatWindow(QtWidgets.QDialog):
    def __init__(self, provider, mcp_manager, config: Dict[str, Any]):
        super().__init__()
        self.provider = provider
        self.mcp = mcp_manager
        self.cfg = config
        
        self.setWindowTitle("💬 AI Chat")
        self.resize(720, 580)
        
        # Message history: [{"role": "user"|"assistant"|"tool", "content": "..."}]
        self.messages: List[Dict[str, str]] = []
        
        # Load chat history if exists
        self._load_history()
        
        self._init_ui()
        self._display_messages()
    
    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        self.btnClear = QtWidgets.QPushButton("🗑️ Clear")
        self.btnExport = QtWidgets.QPushButton("💾 Export")
        toolbar.addStretch(1)
        toolbar.addWidget(self.btnClear)
        toolbar.addWidget(self.btnExport)
        layout.addLayout(toolbar)
        
        # Message display area
        self.chatDisplay = QtWidgets.QTextEdit()
        self.chatDisplay.setReadOnly(True)
        self.chatDisplay.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Segoe UI', Arial;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.chatDisplay, 3)
        
        # Input area
        inputLabel = QtWidgets.QLabel("Your message:")
        layout.addWidget(inputLabel)
        
        self.txtInput = QtWidgets.QPlainTextEdit()
        self.txtInput.setPlaceholderText("Type your message here...")
        self.txtInput.setMaximumHeight(100)
        self.txtInput.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 8px;
                font-family: 'Segoe UI', Arial;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.txtInput)
        
        # Buttons
        btnLayout = QtWidgets.QHBoxLayout()
        self.btnMCP = QtWidgets.QPushButton("📎 MCP Tools")
        self.btnSend = QtWidgets.QPushButton("📤 Send")
        self.btnSend.setDefault(True)
        btnLayout.addWidget(self.btnMCP)
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.btnSend)
        layout.addLayout(btnLayout)
        
        # Connect signals
        self.btnSend.clicked.connect(self._send_message)
        self.btnClear.clicked.connect(self._clear_history)
        self.btnExport.clicked.connect(self._export_chat)
        self.btnMCP.clicked.connect(self._open_mcp_tools)
        
        # Ctrl+Enter to send
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self._send_message)
    
    def _display_messages(self):
        """Display all messages in chat history"""
        html_parts = []
        for msg in self.messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "user":
                html_parts.append(f"""
                <div style='margin: 10px 0; text-align: right;'>
                    <span style='background: #0084ff; color: white; padding: 8px 12px; 
                                 border-radius: 15px; display: inline-block; max-width: 70%;
                                 text-align: left;'>
                        <b>👤 You:</b><br>{self._escape_html(content)}
                    </span>
                </div>
                """)
            elif role == "assistant":
                html_parts.append(f"""
                <div style='margin: 10px 0;'>
                    <span style='background: #e4e6eb; color: black; padding: 8px 12px; 
                                 border-radius: 15px; display: inline-block; max-width: 70%;'>
                        <b>🤖 AI:</b><br>{self._escape_html(content)}
                    </span>
                </div>
                """)
            elif role == "tool":
                html_parts.append(f"""
                <div style='margin: 10px 0;'>
                    <span style='background: #fff3cd; color: #856404; padding: 8px 12px; 
                                 border-radius: 15px; display: inline-block; max-width: 70%;
                                 border: 1px dashed #ffc107;'>
                        <b>🔧 Tool Result:</b><br><pre style='margin: 5px 0; font-size: 9pt;'>{self._escape_html(content)}</pre>
                    </span>
                </div>
                """)
        
        html = "<html><body style='font-family: Segoe UI, Arial;'>" + "".join(html_parts) + "</body></html>"
        self.chatDisplay.setHtml(html)
        
        # Scroll to bottom
        cursor = self.chatDisplay.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.chatDisplay.setTextCursor(cursor)
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML but preserve newlines"""
        import html
        return html.escape(text).replace("\n", "<br>")
    
    def _send_message(self):
        user_msg = self.txtInput.toPlainText().strip()
        if not user_msg:
            return
        
        # Add user message
        self.messages.append({"role": "user", "content": user_msg})
        self.txtInput.clear()
        self._display_messages()
        self._save_history()
        
        # Show "typing" indicator
        self.btnSend.setEnabled(False)
        self.chatDisplay.append("<i>🤖 AI is typing...</i>")
        QtWidgets.QApplication.processEvents()
        
        # Get AI response
        try:
            provider_cfg = self.cfg[self.cfg["provider"]].copy()
            provider_cfg["summary_language"] = self.cfg["ui"].get("summary_language", "vi")
            
            # Call provider chat method
            response = self.provider.chat(self.messages, provider_cfg)
            
            # Add assistant response
            self.messages.append({"role": "assistant", "content": response})
            self._display_messages()
            self._save_history()
        
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            self.messages.append({"role": "assistant", "content": error_msg})
            self._display_messages()
        
        finally:
            self.btnSend.setEnabled(True)
    
    def _open_mcp_tools(self):
        """Open MCP tools dialog and add result to chat"""
        if not self.mcp or not self.mcp.sessions:
            QtWidgets.QMessageBox.warning(self, "MCP", "MCP chưa được kích hoạt hoặc không có server nào kết nối.")
            return
        
        # Import MCP panel from app.py
        from app import MCPPanel
        
        dlg = MCPPanel(self.mcp, self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            if dlg.extra_context:
                # Add tool result as a message
                self.messages.append({"role": "tool", "content": dlg.extra_context})
                self._display_messages()
                self._save_history()
    
    def _clear_history(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Clear History",
            "Bạn có chắc muốn xóa toàn bộ lịch sử chat?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.messages = []
            self._display_messages()
            self._save_history()
    
    def _export_chat(self):
        if not self.messages:
            QtWidgets.QMessageBox.information(self, "Export", "Không có tin nhắn để export.")
            return
        
        default_name = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Chat", default_name, "Text Files (*.txt)"
        )
        if path:
            content = []
            content.append(f"=== AI Chat Export ===")
            content.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content.append(f"Provider: {self.cfg['provider']}")
            content.append("=" * 50)
            content.append("")
            
            for msg in self.messages:
                role = msg["role"]
                if role == "user":
                    content.append("👤 YOU:")
                elif role == "assistant":
                    content.append("🤖 AI:")
                elif role == "tool":
                    content.append("🔧 TOOL RESULT:")
                content.append(msg["content"])
                content.append("")
            
            Path(path).write_text("\n".join(content), encoding="utf-8")
            QtWidgets.QMessageBox.information(self, "Export", f"Chat đã được export: {path}")
    
    def _load_history(self):
        """Load chat history from file"""
        history_path = Path("chat_history.json")
        if history_path.exists():
            try:
                data = json.loads(history_path.read_text(encoding="utf-8"))
                self.messages = data.get("messages", [])
            except Exception:
                self.messages = []
        else:
            self.messages = []
    
    def _save_history(self):
        """Save chat history to file"""
        history_path = Path("chat_history.json")
        data = {"messages": self.messages}
        history_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

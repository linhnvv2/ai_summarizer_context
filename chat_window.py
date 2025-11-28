# chat_window.py
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from PySide6 import QtWidgets, QtGui, QtCore
from ui_components import MCPPanel

class ChatWindow(QtWidgets.QDialog):
    def __init__(self, provider, mcp_manager, config: Dict[str, Any]):
        logging.info("ChatWindow.__init__ started")
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
        
        # Install event filter to handle Enter key
        self.txtInput.installEventFilter(self)
        
        # Remove old shortcut if it exists (optional, but cleaner)
        # shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self)
        # shortcut.activated.connect(self._send_message)

    def eventFilter(self, obj, event):
        if obj is self.txtInput and event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Return and not (event.modifiers() & QtCore.Qt.ShiftModifier):
                self._send_message()
                return True
        return super().eventFilter(obj, event)
    
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
                thinking = msg.get("thinking", "")
                # Remove <think></think> tags from thinking
                thinking_clean = thinking.replace("<think>", "").replace("</think>", "").strip()
                
                html_parts.append(f"""
                <div style='margin: 10px 0;'>
                    <span style='background: #e4e6eb; color: black; padding: 8px 12px; 
                                 border-radius: 15px; display: inline-block; max-width: 70%;'>
                        <b>🤖 AI:</b><br>
                        {f"<details style='margin: 5px 0;'><summary style='color: #856404; cursor: pointer; font-size: 9pt;'>💭 Thinking...</summary><div style='background: #fff3cd; padding: 6px 8px; margin-top: 5px; border-radius: 5px; font-size: 9pt; color: #856404;'>{self._escape_html(thinking_clean)}</div></details>" if thinking_clean else ""}
                        {self._escape_html(content)}
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
        
        # Disable send button
        self.btnSend.setEnabled(False)
        self.btnMCP.setEnabled(False)
        
        # Stream AI response
        try:
            provider_cfg = self.cfg[self.cfg["provider"]].copy()
            provider_cfg["summary_language"] = self.cfg["ui"].get("summary_language", "vi")
            
            # Accumulate streaming content
            thinking_text = ""
            content_text = ""
            
            # Stream chunks
            for chunk in self.provider.chat_stream(self.messages, provider_cfg):
                if chunk["type"] == "thinking":
                    thinking_text += chunk["text"]
                else:
                    content_text += chunk["text"]
                
                # Update display in real-time
                self._update_streaming_message(thinking_text, content_text)
                QtWidgets.QApplication.processEvents()
            
            # Finalize message
            self.messages.append({
                "role": "assistant",
                "content": content_text,
                "thinking": thinking_text
            })
            self._display_messages()
            self._save_history()
        
        except Exception as e:
            logging.error(f"Chat stream error: {e}", exc_info=True)
            error_msg = f"❌ Error: {str(e)}"
            self.messages.append({"role": "assistant", "content": error_msg})
            self._display_messages()
        
        finally:
            self.btnSend.setEnabled(True)
            self.btnMCP.setEnabled(True)
    
    def _update_streaming_message(self, thinking: str, content: str):
        """Update chat display with streaming content"""
        # Build HTML for streaming message
        thinking_clean = thinking.replace("<think>", "").replace("</think>", "").strip()
        
        html_parts = []
        for msg in self.messages:
            role = msg["role"]
            msg_content = msg["content"]
            
            if role == "user":
                html_parts.append(f"""
                <div style='margin: 10px 0; text-align: right;'>
                    <span style='background: #0084ff; color: white; padding: 8px 12px; 
                                 border-radius: 15px; display: inline-block; max-width: 70%;
                                 text-align: left;'>
                        <b>👤 You:</b><br>{self._escape_html(msg_content)}
                    </span>
                </div>
                """)
            elif role == "assistant":
                msg_thinking = msg.get("thinking", "")
                msg_thinking_clean = msg_thinking.replace("<think>", "").replace("</think>", "").strip()
                html_parts.append(f"""
                <div style='margin: 10px 0;'>
                    <span style='background: #e4e6eb; color: black; padding: 8px 12px; 
                                 border-radius: 15px; display: inline-block; max-width: 70%;'>
                        <b>🤖 AI:</b><br>
                        {f"<details style='margin: 5px 0;'><summary style='color: #856404; cursor: pointer; font-size: 9pt;'>💭 Thinking...</summary><div style='background: #fff3cd; padding: 6px 8px; margin-top: 5px; border-radius: 5px; font-size: 9pt; color: #856404;'>{self._escape_html(msg_thinking_clean)}</div></details>" if msg_thinking_clean else ""}
                        {self._escape_html(msg_content)}
                    </span>
                </div>
                """)
            elif role == "tool":
                html_parts.append(f"""
                <div style='margin: 10px 0;'>
                    <span style='background: #fff3cd; color: #856404; padding: 8px 12px; 
                                 border-radius: 15px; display: inline-block; max-width: 70%;
                                 border: 1px dashed #ffc107;'>
                        <b>🔧 Tool Result:</b><br><pre style='margin: 5px 0; font-size: 9pt;'>{self._escape_html(msg_content)}</pre>
                    </span>
                </div>
                """)
        
        # Add streaming message
        if content or thinking:
            html_parts.append(f"""
            <div style='margin: 10px 0;'>
                <span style='background: #e4e6eb; color: black; padding: 8px 12px; 
                             border-radius: 15px; display: inline-block; max-width: 70%;'>
                    <b>🤖 AI:</b> <i style='color: #666;'>typing...</i><br>
                    {f"<div style='background: #fff3cd; padding: 4px 8px; margin: 4px 0; border-radius: 5px; font-size: 9pt; color: #856404;'>💭 {self._escape_html(thinking_clean)}</div>" if thinking_clean else ""}
                    {self._escape_html(content)}<span style='animation: blink 1s infinite;'>▊</span>
                </span>
            </div>
            """)
        
        html = "<html><head><style>@keyframes blink { 50% { opacity: 0; } }</style></head><body style='font-family: Segoe UI, Arial;'>" + "".join(html_parts) + "</body></html>"
        self.chatDisplay.setHtml(html)
        
        # Scroll to bottom
        cursor = self.chatDisplay.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.chatDisplay.setTextCursor(cursor)
    
    def _open_mcp_tools(self):
        """Open MCP tools dialog and add result to chat"""
        if not self.mcp or not self.mcp.sessions:
            QtWidgets.QMessageBox.warning(self, "MCP", "MCP chưa được kích hoạt hoặc không có server nào kết nối.")
            return
        
        # Import MCP panel from ui_components
        from ui_components import MCPPanel
        
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

    def add_context(self, text: str):
        """Add context (e.g. summary result) as an AI message if not already present"""
        # Check if the last message is the same to avoid duplicates
        if self.messages and self.messages[-1]["content"] == text:
            return
            
        self.messages.append({"role": "assistant", "content": text})
        self._display_messages()
        self._save_history()
        
        # Scroll to bottom
        cursor = self.chatDisplay.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.chatDisplay.setTextCursor(cursor)

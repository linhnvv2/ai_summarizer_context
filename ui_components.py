import json
import datetime
import logging
from pathlib import Path
from PySide6 import QtWidgets, QtGui, QtCore
from mcp_manager import MCPManager

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
        self.btnRewrite = QtWidgets.QPushButton("✍️ Viết lại")
        self.btnCustom = QtWidgets.QPushButton("⚙️ Prompt tùy biến")
        self.btnClose = QtWidgets.QPushButton("❌ Đóng")

        for b in (self.btnSummary, self.btnExplain, self.btnTranslate, self.btnRewrite, self.btnCustom, self.btnClose):
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            self.layout().addWidget(b)

        self.textOriginal = ""
        self.callback = None
        
        # Kết nối signals
        self.btnSummary.clicked.connect(lambda: self._do("summary"))
        self.btnExplain.clicked.connect(lambda: self._do("explain"))
        self.btnTranslate.clicked.connect(lambda: self._do("translate"))
        self.btnRewrite.clicked.connect(lambda: self._do("rewrite"))
        self.btnCustom.clicked.connect(lambda: self._do("custom"))
        self.btnClose.clicked.connect(self.hide)

    def show_at_cursor(self, pos: QtCore.QPoint, text: str, callback):
        self.textOriginal = text
        self.callback = callback
        self.move(pos)
        self.show()
        self.activateWindow()
        self.raise_()

    def _do(self, action: str):
        self.hide()
        if self.callback:
            self.callback(action, self.textOriginal)

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
            logging.info(f"UI requesting tool execution: {server}/{tool} with args {args}")
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
            logging.error(f"UI Tool execution failed: {e}", exc_info=True)
            self.txtResult.setPlainText(f"❌ Lỗi chạy tool: {e}")
            self.extra_context = ""

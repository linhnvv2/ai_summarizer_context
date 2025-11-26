# AI Summarizer + MCP (Windows Desktop)

Ứng dụng desktop chạy nền (system tray) cho Windows:
- Bôi đen văn bản → **Shift + chuột phải** → panel hành động.
- Gọi **LLM cục bộ** (Ollama hoặc LM Studio) để **tóm tắt/giải thích/dịch**.
- **Tích hợp MCP**: chọn server/tool, chạy tool (filesystem, web, DB…), lấy kết quả làm **ngữ cảnh** trước khi tóm tắt.

## Tính năng
- Popup hành động cạnh con trỏ: Tóm tắt, Giải thích, Dịch, Prompt tuỳ biến.
- Provider: **Ollama** (`/api/generate`) hoặc **LM Studio** (OpenAI-compatible `/v1/chat/completions`).
- **MCP Panel**: liệt kê servers/tools, nhập args JSON, chạy tool và chèn kết quả vào prompt.
- Bảo mật: Mặc định chỉ gọi endpoint **local** và MCP servers cục bộ.

## Yêu cầu hệ thống
- **Windows 10/11**
- Python 3.10+ (khuyến nghị 64-bit)
- Node.js (để chạy MCP filesystem server qua `npx`)

## Cài đặt
```bash
# 1) Tạo venv và cài thư viện
python -m venv .venv
.venv\Scripts\activate
pip install PySide6 pynput pywin32 requests "mcp[cli]" python-dotenv

# 2) (Tuỳ chọn) Đóng gói .exe
pip install pyinstaller
pyinstaller -F -w app.py
```

> **Gợi ý model cục bộ** (máy i7-14700K, RAM 64GB): `llama3.2:3b-instruct`, `mistral:7b-instruct` (Q4), `phi3.1:3.8b`. Ollama nhanh & đơn giản.

## Cấu hình
Lần chạy đầu sẽ tạo `config.json`. Bạn có thể sửa qua menu **Cấu hình…** hoặc trực tiếp file.
```json
{
  "provider": "ollama",
  "ollama": {
    "endpoint": "http://127.0.0.1:11434",
    "model": "llama3.2:3b-instruct",
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
    "summary_language": "vi",
    "trigger": {"modifier": "shift", "button": "right"}
  },
  "mcp": {
    "enabled": true,
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
```
> **Lưu ý**: Dùng **forward slash** `/` hoặc escape backslash `\\` trong JSON đường dẫn.

## Chạy providers
### Ollama
```bash
# Cài và chạy server
# https://ollama.com 
ollama serve
ollama pull llama3.2:3b-instruct
```
### LM Studio
- Mở LM Studio → Tab **Server** → chọn model → **Start Server** (mặc định `http://127.0.0.1:1234/v1`).

## Chạy MCP servers
Ví dụ **Filesystem server** qua `npx` (Node.js):
- Ứng dụng sẽ tự khởi chạy server qua cấu hình stdio.
- Bạn có thể thay `ROOT_PATH` để giới hạn phạm vi đọc/ghi.

## Sử dụng
1. Chạy `python app.py` (hoặc mở `dist/app.exe`).
2. Biểu tượng máy tính xuất hiện ở **system tray**.
3. Bôi đen văn bản → giữ **Shift** → **Click chuột phải**.
4. Chọn hành động: Tóm tắt / Giải thích / Dịch / Prompt.
5. Để thêm ngữ cảnh từ MCP:
   - Mở menu tray → **MCP: Panel chọn server/tool**.
   - Chọn **server**, **tool**, nhập **args JSON** → **Chạy tool**.
   - Tick **“Dùng kết quả làm ngữ cảnh tóm tắt”** → **Đóng**.
   - Thực hiện tóm tắt như bước 3–4.

## Đóng gói .exe
```bash
pyinstaller -F -w app.py
# File tạo tại dist/app.exe
```

## Thư mục dự án
```
ai_summarizer_mcp/
├─ app.py
├─ README.md
├─ requirements.txt
└─ (tự sinh) config.json sau lần chạy đầu
```

## Troubleshooting
- **Không copy được selection**: Một số app chặn `Ctrl+C`. Hãy nhấn `Ctrl+C` thủ công trước rồi dùng gesture.
- **Ollama 404/timeout**: Kiểm tra `ollama serve` và model đã `pull`.
- **MCP server không hiện tools**: Kiểm tra Node.js, thử chạy thủ công `npx @modelcontextprotocol/server-filesystem`.
- **LM Studio trả lỗi**: Đảm bảo endpoint `/v1` và model đúng tên.

## Ghi chú & chuẩn MCP
- MCP là chuẩn mở (Anthropic) cho tools/resources/prompts; SDK Python hỗ trợ client–server và stdio/HTTP/SSE transport.
- Tham khảo: Model Context Protocol Python SDK & hướng dẫn Build an MCP client.


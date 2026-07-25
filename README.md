# HuyG Agent Series — Bài 2: Xây AI Agent biết PHỐI HỢP nhiều tool (có UI)

> Bài này ta dựng một **AI Agent** — một LLM biết **tự quyết định** dùng công cụ
> (tool) để trả lời. Điểm nhấn: agent có thể **phối hợp nhiều tool trong một câu hỏi**
> (đọc PDF → tính toán → đổi tiền tệ). Có sẵn giao diện chat. Code tối giản, chú thích
> tiếng Việt đầy đủ, giải thích rõ *tại sao* chọn từng tham số/phương pháp.

---

## 1. Agent là gì? (30 giây)

Một LLM bình thường chỉ biết sinh chữ. **Agent** bọc thêm cho nó một *vòng lặp có suy
nghĩ*: model tự nhìn câu hỏi rồi **chọn** làm gì — đọc PDF? bấm máy tính? đổi tiền? hay
trả lời thẳng? — làm xong **quan sát** kết quả rồi đi bước tiếp theo, cho tới khi đủ
dữ kiện để trả lời.

```
        ┌────────────────── VÒNG LẶP AGENT (mỗi câu hỏi) ──────────────────┐
 Câu hỏi ─► LLM suy nghĩ ─► cần tool? ──có──► chạy tool ─► đưa kết quả về ─┐
                              │  không                                     │
                              ▼                                            │
                          Trả lời  ◄───────────────(lặp lại)──────────────┘
        └──────────────────────────────────────────────────────────────────┘
```

Ba từ khoá: **Suy nghĩ → Hành động (gọi tool) → Quan sát** (Think → Act → Observe).

---

## 2. Cấu trúc thư mục

```
Agent_Series/
├── .env                      # cấu hình THẬT (đã điền sẵn key Gemini) — KHÔNG commit
├── .env.example              # mẫu cấu hình cho mọi provider
├── requirements.txt          # danh sách thư viện (nhẹ, không cần torch)
├── run.ps1                   # script 1-chạm cho Windows (tạo venv, cài, mở app)
├── README.md                 # file bạn đang đọc
├── app.py                    # 🖥️ giao diện chat (Streamlit)
│
├── agent_core/               # 🧠 package chính — mỗi file một nhiệm vụ
│   ├── config.py             #   đọc .env, chọn provider
│   ├── tools.py              #   khai báo 3 tool: read_pdf, calculator, convert_currency
│   ├── providers.py          #   "phiên dịch" giữa agent và Gemini/Claude/OpenAI
│   └── agent.py              #   ⭐ VÒNG LẶP AGENT (phần cốt lõi, không phụ thuộc hãng)
│
└── scripts/
    └── chat_cli.py           # chat với agent trong terminal (không cần UI)
```

**Vì sao tách nhỏ vậy?** Mỗi file một việc → dễ đọc, dễ dạy, dễ thay thế. Muốn thêm
tool mới chỉ sửa `tools.py`; muốn thêm nhà cung cấp LLM chỉ sửa `providers.py`; phần
"bộ não" (`agent.py`) không phải đụng tới.

---

## 3. Cài đặt — làm theo thứ tự

> Yêu cầu: Python 3.10+. Cài đặt bài này **nhẹ và nhanh** (không kéo theo torch).

### Cách nhanh (Windows): 1 lệnh

```powershell
.\run.ps1
```

Script sẽ tự tạo venv, cài thư viện, tạo `.env` (nếu chưa có) và mở giao diện.

### Cách thủ công (hiểu từng bước)

```powershell
# 1) Tạo & kích hoạt môi trường ảo
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Cài thư viện
pip install -r requirements.txt

# 3) Tạo file cấu hình
Copy-Item .env.example .env
# -> mở .env, dán API key (mặc định đã dùng Gemini)
```

> 💡 File `.env` trong repo này **đã điền sẵn** một key Gemini để chạy được ngay. Khi
> phát cho học viên, hãy để họ tự điền key của mình (lấy miễn phí ở
> https://aistudio.google.com/apikey).

---

## 4. Chạy thử

### Giao diện chat (khuyến khích)

```powershell
streamlit run app.py
```

Trình duyệt mở ra ô chat. Thử vài câu:

| Bạn hỏi | Agent sẽ tự làm gì |
|---|---|
| `100 USD đổi ra bao nhiêu VND?` | gọi tool **convert_currency** |
| `15% của 2.000.000 là bao nhiêu, rồi đổi sang USD?` | **calculator** → **convert_currency** (2 tool nối tiếp) |
| `Đọc file D:/baogia.pdf, cộng các khoản rồi đổi sang USD` | **read_pdf** → **calculator** → **convert_currency** (3 tool!) |
| `Xin chào, bạn là ai?` | trả lời thẳng, không cần tool |

Bấm **"🔍 Agent đã làm gì?"** dưới mỗi câu trả lời để xem agent đã gọi tool nào, theo
thứ tự nào — đây chính là chỗ thấy rõ agent **phối hợp** tool.

### Terminal (không cần UI)

```powershell
python scripts/chat_cli.py "100 USD bang bao nhieu VND?"
python scripts/chat_cli.py        # chế độ hỏi–đáp liên tục
```

---

## 5. Luồng dữ liệu chạy qua code như thế nào?

Khi bạn gõ một câu hỏi, `agent.run()` trong `agent.py` làm việc này:

| # | File | Việc làm |
|---|------|----------|
| 1 | `providers.py` | Gửi lịch sử hội thoại + danh sách tool cho LLM, nhận về "muốn gọi tool nào" hay "câu trả lời" |
| 2 | `agent.py` | Nếu model muốn gọi tool → chạy tool, đưa kết quả lại rồi **lặp lại** bước 1 |
| 3 | `tools.py` | Tool thực thi và trả về chuỗi kết quả |
| 4 | `agent.py` | Khi model không gọi tool nữa → trả `AgentResult(text, steps)` |

Điểm hay: **vòng lặp ở `agent.py` viết đúng một lần** mà chạy được với cả Gemini,
Claude và OpenAI, nhờ lớp "phiên dịch" trong `providers.py` chuẩn hoá tin nhắn về một
định dạng chung. Nhờ vòng lặp này, model có thể gọi tool **nhiều lần liên tiếp** để
phối hợp (kết quả read_pdf làm đầu vào cho calculator, rồi cho convert_currency).

---

## 6. Đổi nhà cung cấp LLM (Gemini / Claude / OpenAI)

Chỉ cần sửa `.env`:

```dotenv
LLM_PROVIDER=anthropic          # đổi thành nhà cung cấp bạn muốn
ANTHROPIC_API_KEY=sk-ant-...    # điền key tương ứng
```

- **gemini** — mặc định, miễn phí.
- **anthropic** (Claude) — cần key ở https://console.anthropic.com/. Muốn rẻ: đặt
  `ANTHROPIC_MODEL=claude-haiku-4-5`.
- **openai** (GPT/Codex) — cần key ở https://platform.openai.com/api-keys.

> Đường **đã kiểm thử kỹ** là Gemini. Hai đường còn lại viết theo đúng một ý tưởng
> (xem `providers.py`) — dán key vào là chạy, nhưng bạn nên tự kiểm tra với tài khoản
> của mình vì tên model mỗi hãng thay đổi theo thời gian.

---

## 7. Các tool đang có (và cách thêm tool mới)

| Tool | Việc | Minh hoạ điều gì |
|---|---|---|
| `read_pdf` | Đọc nội dung văn bản từ file PDF | tool đọc **file** |
| `calculator` | Tính biểu thức số học **an toàn** (không dùng `eval()`) | tool **tính toán** |
| `convert_currency` | Đổi tiền tệ theo bảng tỷ giá cố định (offline) | tool có **nhiều tham số** + tra bảng |

**Thêm tool mới rất đơn giản** — trong `tools.py`, thêm một `ToolSpec` vào
`build_default_registry()`:

```python
ToolSpec(
    name="ten_tool",
    description="Mô tả rõ KHI NÀO model nên gọi tool này.",
    parameters={"type": "object",
                "properties": {"x": {"type": "string", "description": "..."}},
                "required": ["x"]},
    func=ham_python_that_su,   # nhận x, trả về chuỗi kết quả
)
```

Không cần đụng tới `agent.py` hay `providers.py`.

---

## 8. Vì sao chọn tham số / phương pháp này? (ghi chú thiết kế)

- **`temperature` thấp (0.2):** agent cần **quyết định gọi tool ổn định**, không cần
  bay bổng. Số thấp → ít ngẫu nhiên, ít bịa. *(Model Claude đời mới bỏ tham số này —
  đó là lý do `AnthropicClient` cố ý không gửi nó.)*
- **`max_steps = 5`:** *phanh an toàn* chống lặp vô hạn (model lỡ gọi tool mãi không
  dừng). Vì một câu hỏi có thể cần vài tool nối tiếp, ta cho ≥ số tool + dư một chút.
- **Tắt "automatic function calling" của Gemini:** để **tự viết vòng lặp** trong
  `agent.py`, nhờ vậy bạn **nhìn thấy** từng bước phối hợp tool, thay vì SDK làm giúp
  rồi giấu đi (mục tiêu là để học).
- **Máy tính dùng AST thay vì `eval()`:** `eval()` chạy được **mọi** câu lệnh Python
  (kể cả xoá file) — cực nguy hiểm khi đầu vào do model sinh. Ta chỉ mở đúng các phép
  toán cần thiết.
- **`convert_currency` dùng bảng tỷ giá cố định:** để chạy **offline, không cần API
  key** — học viên chạy được ngay; mục tiêu là dạy *điều phối tool*, không phải lấy
  tỷ giá chính xác. Lên thực tế chỉ cần thay hàm bằng lời gọi API tỷ giá.
- **Bọc mọi tool trong try/except:** tool lỗi thì trả lỗi **dưới dạng văn bản** để
  agent đọc được và tự sửa, thay vì làm sập chương trình.
- **Lịch sử hội thoại chuẩn hoá:** để **một** vòng lặp chạy được với **mọi** provider.
- **Gemini cần replay `thought_signature`:** một "gotcha" thật của Gemini đời mới —
  khi gửi lại function_call ở lượt sau phải kèm đúng "chữ ký suy nghĩ" model đã sinh,
  nếu thiếu sẽ lỗi 400. Xem chú thích trong `providers.py`.

---

## 9. Lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| `Thiếu GEMINI_API_KEY...` | Chưa tạo `.env` hoặc chưa dán key. Xem mục 3. |
| `ModuleNotFoundError: anthropic/openai` | Provider đó chưa cài. Chạy lại `pip install -r requirements.txt`. |
| `[Lỗi] Không tìm thấy file` khi đọc PDF | Kiểm tra lại đường dẫn file PDF bạn đưa cho agent. |
| PDF "không trích được chữ" | File là ảnh scan — cần OCR (ngoài phạm vi bài này). |
| `429 / 503` khi hỏi | Server LLM quá tải hoặc hết quota free tạm thời. Đợi chút rồi thử lại. |

---

## 10. Bài tập mở rộng (cho học viên tự luyện)

1. Thêm tool `get_current_time` (trả về giờ hiện tại) — tool **không cần tham số**.
2. Thêm vài loại tiền vào bảng tỷ giá trong `convert_currency`.
3. Cho agent **nhớ tên bạn** qua nhiều câu hỏi (trí nhớ nằm ở `agent.history`).
4. Đổi `AGENT_MAX_STEPS` = 1 rồi hỏi câu cần 3 tool — quan sát điều gì xảy ra.
5. **Nối lại với series RAG:** thêm tool `search_knowledge_base` gọi `RAGPipeline` từ
   project RAG (`D:/HuyG-RAG-Series`) — khi đó agent vừa tra tài liệu, vừa tính toán,
   vừa đổi tiền. (Chỉ cần thêm 1 `ToolSpec`, không đụng phần lõi.)

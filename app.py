"""Giao diện chat cho AI Agent — viết bằng Streamlit (thư viện làm web UI bằng Python).

Vì sao chọn Streamlit? Vì nó cho phép dựng giao diện chat CHỈ bằng Python, không cần
biết HTML/JS. Rất hợp để học viên tập trung vào TƯ DUY agent thay vì loay hoay giao diện.
  - st.chat_message(...) : ô hội thoại (người dùng / trợ lý)
  - st.chat_input(...)   : ô nhập câu hỏi ở dưới cùng
  - st.session_state     : "bộ nhớ" giữ lại giữa các lần tương tác (Streamlit chạy lại
                           toàn bộ file mỗi khi bạn gõ, nên cần chỗ này để nhớ hội thoại)

Chạy:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from agent_core.agent import Agent
from agent_core.config import load_settings
from agent_core.providers import build_client
from agent_core.runtime import build_tool_registry

# ---------- Cấu hình trang ----------
st.set_page_config(page_title="AI Agent + RAG", page_icon="🤖", layout="centered")
st.title("🤖 AI Agent (có dùng RAG làm tool)")


# ---------- Khởi tạo agent MỘT LẦN và giữ trong session_state ----------
# @st.cache_resource: Streamlit chỉ chạy hàm này 1 lần rồi giữ kết quả (kể cả khi
# file chạy lại). Nhờ vậy client LLM không bị tạo đi tạo lại mỗi lần gõ phím.
@st.cache_resource
def create_agent() -> Agent:
    settings = load_settings()             # đọc .env, có thể ném lỗi nếu thiếu key
    client = build_client(settings)        # chọn provider theo .env
    registry = build_tool_registry(settings)  # tool Python nội bộ + tool MCP được khám phá
    return Agent(client, registry, max_steps=settings.max_steps)


# Nếu thiếu cấu hình (chưa có key...), báo lỗi thân thiện rồi dừng — không cho crash xấu.
try:
    settings = load_settings()
    agent = create_agent()
except Exception as e:  # noqa: BLE001
    st.error(f"❌ Chưa chạy được agent:\n\n{e}")
    st.info("Gợi ý: sao chép `.env.example` thành `.env` rồi điền API key, xem README.md.")
    st.stop()


# ---------- Thanh bên: cho biết đang dùng provider/model nào + nút xoá hội thoại ----------
with st.sidebar:
    st.header("⚙️ Cấu hình")
    st.write(f"**Nhà cung cấp:** `{settings.provider}`")
    st.write(f"**Model:** `{settings.active_model}`")
    st.write("**Tool đang có:**")
    for spec in agent.registry.specs():
        st.write(f"- `{spec.name}`")
    st.caption(f"Tối đa {settings.max_steps} bước suy luận mỗi câu hỏi.")

    if st.button("🗑️ Xoá hội thoại"):
        agent.reset()                       # xoá trí nhớ của agent
        st.session_state.messages = []      # xoá phần hiển thị
        st.rerun()

# "messages" chỉ để HIỂN THỊ lại lịch sử trên màn hình (agent tự giữ trí nhớ riêng).
if "messages" not in st.session_state:
    st.session_state.messages = []


# ---------- Vẽ lại toàn bộ hội thoại đã có ----------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Với câu trả lời của trợ lý, cho xem chi tiết các bước gọi tool (nếu có).
        if msg["role"] == "assistant" and msg.get("steps"):
            with st.expander("🔍 Agent đã làm gì?"):
                for s in msg["steps"]:
                    st.markdown(f"**🔧 Gọi tool `{s.tool}`** với tham số: `{s.args}`")
                    st.code(s.result, language="text")


# ---------- Nhận câu hỏi mới từ người dùng ----------
if prompt := st.chat_input("Nhập câu hỏi cho agent..."):
    # 1) Hiển thị + lưu câu người dùng
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2) Để agent xử lý, hiển thị tiến trình gọi tool ngay trong lúc chạy
    with st.chat_message("assistant"):
        status = st.status("Agent đang suy nghĩ...", expanded=True)

        # Callback này được agent gọi mỗi khi nó gọi tool / nhận kết quả tool.
        def on_step(ev: dict) -> None:
            if ev["type"] == "tool_call":
                status.write(f"🔧 Gọi tool `{ev['name']}` với `{ev['args']}`")
            elif ev["type"] == "tool_result":
                preview = ev["result"][:300]
                status.write(f"📥 Kết quả (rút gọn): {preview}")

        try:
            result = agent.run(prompt, on_step=on_step)
            status.update(label="Đã xong ✅", state="complete", expanded=False)
            st.markdown(result.text)
        except Exception as e:  # noqa: BLE001
            status.update(label="Có lỗi ⚠️", state="error")
            result_text = f"⚠️ Lỗi khi gọi model: {e}"
            st.markdown(result_text)
            st.session_state.messages.append({"role": "assistant", "content": result_text})
            st.stop()

    # 3) Lưu câu trả lời + các bước để lần sau vẽ lại
    st.session_state.messages.append({
        "role": "assistant",
        "content": result.text,
        "steps": result.steps,
    })

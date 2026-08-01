"""CLI — trò chuyện với agent ngay trong terminal (không cần UI).

Dùng để kiểm tra nhanh agent hoạt động, hoặc để hiểu luồng chạy mà không vướng
giao diện. Cách dùng:

    python scripts/chat_cli.py "RAG gồm những bước nào?"   # hỏi 1 câu rồi thoát
    python scripts/chat_cli.py                              # chế độ hỏi–đáp liên tục
"""

import sys
from pathlib import Path

# In được tiếng Việt + emoji trên terminal Windows (mặc định hay dùng cp1252).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Cho phép `import agent_core` khi chạy trực tiếp file trong thư mục scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core.agent import Agent  # noqa: E402
from agent_core.config import load_settings  # noqa: E402
from agent_core.providers import build_client  # noqa: E402
from agent_core.runtime import build_tool_registry  # noqa: E402


def build_agent() -> Agent:
    settings = load_settings()
    print(f"🔌 Provider: {settings.provider} | Model: {settings.active_model}\n")
    client = build_client(settings)
    registry = build_tool_registry(settings)
    return Agent(client, registry, max_steps=settings.max_steps)


def ask_once(agent: Agent, question: str) -> None:
    """Hỏi 1 câu, in ra tiến trình gọi tool + câu trả lời cuối."""

    def on_step(ev: dict) -> None:
        if ev["type"] == "tool_call":
            print(f"  🔧 Gọi tool {ev['name']} với {ev['args']}")
        elif ev["type"] == "tool_result":
            print(f"  📥 Kết quả (rút gọn): {ev['result'][:200]}")

    result = agent.run(question, on_step=on_step)
    print(f"\n🤖 {result.text}\n")


def main() -> None:
    agent = build_agent()

    # Có câu hỏi truyền từ dòng lệnh -> trả lời một lần rồi thoát.
    if len(sys.argv) > 1:
        ask_once(agent, " ".join(sys.argv[1:]))
        return

    # Ngược lại -> chế độ hỏi–đáp liên tục (gõ 'exit' để thoát).
    print("💬 Chat với AI Agent (gõ 'exit' để thoát)")
    while True:
        try:
            question = input("\n❓ Bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"exit", "quit", "thoat", "q"}:
            break
        if question:
            ask_once(agent, question)


if __name__ == "__main__":
    main()

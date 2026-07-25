"""Cấu hình tập trung cho AI Agent — đọc mọi thứ từ file .env về một đối tượng.

Ý tưởng giống hệt bài RAG: gom hết cấu hình (API key, tên model, tham số) vào MỘT
chỗ duy nhất, các module khác chỉ nhận `Settings` mà không cần biết biến môi trường
nằm ở đâu. Nhờ vậy đổi provider / đổi model chỉ cần sửa .env, không đụng vào code.

Điểm mới so với bài RAG: agent này hỗ trợ NHIỀU nhà cung cấp LLM (provider). Bạn chỉ
cần điền key của provider mình có (Gemini / Claude / OpenAI) rồi đặt LLM_PROVIDER cho
đúng. Mặc định dùng Gemini vì nó tái sử dụng luôn API key của project RAG.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Thư mục gốc của project agent = lùi 1 cấp từ file này: agent_core/config.py -> <root>
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Nạp biến môi trường từ .env ở gốc project agent (nếu có).
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Toàn bộ cấu hình của agent, gom về một chỗ (immutable cho an toàn)."""

    # --- Chọn nhà cung cấp LLM đang dùng: "gemini" | "anthropic" | "openai" ---
    provider: str

    # --- API key + tên model cho TỪNG provider (chỉ cái đang chọn mới bắt buộc) ---
    gemini_api_key: str
    gemini_model: str
    anthropic_api_key: str
    anthropic_model: str
    openai_api_key: str
    openai_model: str

    # --- Tham số điều khiển "bộ não" của agent ---
    # temperature: độ "sáng tạo/ngẫu nhiên" của model. Với AGENT ta để THẤP (0.0–0.3)
    #   vì mục tiêu là ra quyết định gọi tool ỔN ĐỊNH, ít bịa; không cần văn hoa.
    temperature: float
    # max_steps: số vòng "suy nghĩ -> gọi tool -> quan sát" tối đa cho mỗi câu hỏi.
    #   Đây là "phanh an toàn": nếu model lỡ lặp vô hạn (gọi tool mãi không dừng) thì
    #   vẫn thoát ra được, tránh treo và tránh đốt quota. 5 là đủ cho demo nhiều tool.
    max_steps: int
    # max_tokens: giới hạn độ dài câu trả lời model sinh ra mỗi lượt. Đặt vừa phải để
    #   không tốn quota vô ích; Anthropic BẮT BUỘC tham số này nên ta luôn khai báo.
    max_tokens: int

    # ---- Vài tiện ích đọc nhanh cấu hình của provider đang chọn ----
    @property
    def active_api_key(self) -> str:
        return {
            "gemini": self.gemini_api_key,
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
        }[self.provider]

    @property
    def active_model(self) -> str:
        return {
            "gemini": self.gemini_model,
            "anthropic": self.anthropic_model,
            "openai": self.openai_model,
        }[self.provider]


def load_settings() -> Settings:
    """Đọc cấu hình từ môi trường và trả về đối tượng Settings.

    Ném lỗi RÕ RÀNG nếu thiếu key của provider đang chọn — để bạn biết ngay phải làm gì.
    """
    # .strip().lower() để tránh lỗi vặt do gõ dư dấu cách hoặc viết HOA trong .env
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider not in {"gemini", "anthropic", "openai"}:
        raise RuntimeError(
            f"LLM_PROVIDER='{provider}' không hợp lệ. "
            "Chỉ nhận: gemini | anthropic | openai (sửa trong .env)."
        )

    settings = Settings(
        provider=provider,
        # Gemini: mặc định 'gemini-flash-latest' — nhanh, rẻ, hợp để học/demo.
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip(),
        # Anthropic (Claude): mặc định model mạnh nhất; muốn rẻ hơn đổi sang
        # 'claude-haiku-4-5' trong .env. Xem chú thích ở .env.example.
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8").strip(),
        # OpenAI (Codex/GPT): mặc định model gọn nhẹ; bạn tự đổi theo model mình có.
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        temperature=float(os.getenv("AGENT_TEMPERATURE", "0.2")),
        max_steps=int(os.getenv("AGENT_MAX_STEPS", "5")),
        max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "2048")),
    )

    # Kiểm tra key của ĐÚNG provider đang chọn (các provider khác không cần key).
    if not settings.active_api_key:
        env_name = {
            "gemini": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }[provider]
        raise RuntimeError(
            f"Thiếu {env_name} cho provider '{provider}'.\n"
            "-> Hãy sao chép .env.example thành .env rồi điền API key tương ứng.\n"
            "   (Với Gemini: lấy key miễn phí ở https://aistudio.google.com/apikey)"
        )

    return settings

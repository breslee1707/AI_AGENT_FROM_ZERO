"""⭐ VÒNG LẶP AGENT — phần cốt lõi, KHÔNG phụ thuộc nhà cung cấp LLM.

Đây là thứ biến một LLM (chỉ biết sinh chữ) thành một AGENT (biết hành động). Ý tưởng
kinh điển: vòng lặp "Suy nghĩ → Hành động → Quan sát" (Think → Act → Observe):

    1. Đưa câu hỏi + danh sách tool cho model.
    2. Model trả về: hoặc là CÂU TRẢ LỜI cuối cùng, hoặc là YÊU CẦU GỌI TOOL.
    3. Nếu nó muốn gọi tool -> ta chạy tool, đưa kết quả lại cho model, rồi lặp lại (2).
    4. Nếu nó đã trả lời (không gọi tool nữa) -> xong, trả kết quả cho người dùng.

Vì lịch sử hội thoại đã được chuẩn hoá (xem providers.py), vòng lặp này viết MỘT lần
và chạy được với mọi provider. Học viên chỉ cần đọc đúng hàm `run()` là hiểu agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .prompts import DEFAULT_SYSTEM_PROMPT
from .tools.registry import ToolRegistry

# Backward-compatible import for code that previously used agent.SYSTEM_PROMPT.
SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT


@dataclass
class Step:
    """Một bước agent đã thực hiện: gọi tool gì, với tham số gì, nhận kết quả gì.

    Dùng để hiển thị cho người dùng thấy agent đã "suy nghĩ" ra sao (rất hữu ích để dạy).
    """

    tool: str
    args: dict
    result: str


@dataclass
class AgentResult:
    """Kết quả cuối cùng trả cho người dùng."""

    text: str                        # câu trả lời cuối
    steps: list[Step] = field(default_factory=list)  # các bước gọi tool đã đi qua


class Agent:
    def __init__(
        self,
        client,                       # một LLMClient từ providers.py
        registry: ToolRegistry,       # bộ tool agent được dùng
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_steps: int = 5,
    ):
        self.client = client
        self.registry = registry
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        # Lịch sử hội thoại (dạng chuẩn hoá). Giữ trong agent để hỗ trợ chat NHIỀU LƯỢT:
        # model nhớ được những gì đã nói ở các câu trước.
        self.history: list[dict] = []

    def reset(self) -> None:
        """Xoá lịch sử để bắt đầu cuộc trò chuyện mới."""
        self.history = []

    def run(
        self,
        user_text: str,
        on_step: Optional[Callable[[dict], None]] = None,
    ) -> AgentResult:
        """Xử lý MỘT câu hỏi của người dùng, trả về câu trả lời cuối + các bước đã đi.

        `on_step` (tuỳ chọn): hàm callback để báo cho UI biết agent vừa gọi tool nào —
        nhờ đó UI hiển thị tiến trình trực tiếp. Nếu không truyền thì bỏ qua.
        """
        # Thêm câu người dùng vào lịch sử.
        self.history.append({"role": "user", "content": user_text})
        steps: list[Step] = []

        # Vòng lặp có GIỚI HẠN số bước (phanh an toàn chống lặp vô hạn).
        for _ in range(self.max_steps):
            # (A) Hỏi model: dựa trên lịch sử + danh sách tool, bạn muốn làm gì?
            reply = self.client.complete(
                self.system_prompt, self.history, self.registry.specs()
            )

            # Ghi lại lượt của model vào lịch sử (kèm các tool nó muốn gọi, nếu có).
            self.history.append({
                "role": "assistant",
                "content": reply.text,
                "tool_calls": reply.tool_calls,
            })

            # (B) Nếu model KHÔNG gọi tool nữa -> nó đã trả lời xong.
            if not reply.tool_calls:
                return AgentResult(text=reply.text, steps=steps)

            # (C) Model muốn gọi tool -> chạy TẤT CẢ tool nó yêu cầu, rồi đưa kết quả lại.
            for call in reply.tool_calls:
                if on_step:
                    on_step({"type": "tool_call", "name": call["name"], "args": call["args"]})

                result = self.registry.run(call["name"], call["args"])
                steps.append(Step(tool=call["name"], args=call["args"], result=result))

                if on_step:
                    on_step({"type": "tool_result", "name": call["name"], "result": result})

                # Đưa kết quả tool vào lịch sử để model "quan sát" ở vòng lặp kế tiếp.
                self.history.append({
                    "role": "tool",
                    "id": call["id"],
                    "name": call["name"],
                    "content": result,
                })
            # Quay lại đầu vòng lặp: model xem kết quả tool rồi quyết định bước tiếp theo.

        # Nếu chạm giới hạn số bước mà vẫn chưa xong -> dừng an toàn và báo cho người dùng.
        return AgentResult(
            text=(
                "Xin lỗi, mình đã đạt giới hạn số bước suy luận mà chưa hoàn tất. "
                "Bạn thử hỏi cụ thể hơn giúp mình nhé."
            ),
            steps=steps,
        )

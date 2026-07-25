"""Package `agent_core` — một AI Agent tối giản, dễ đọc, có UI.

AI Agent = một LLM (bộ não) + vòng lặp cho phép nó TỰ QUYẾT ĐỊNH gọi "công cụ" (tool)
để lấy thêm thông tin/hành động, rồi quan sát kết quả và trả lời. Điểm nhấn của bài này
là cho agent PHỐI HỢP nhiều tool trong một câu hỏi (đọc PDF -> tính toán -> đổi tiền).

Đọc code theo thứ tự sau là hiểu trọn agent:
  config.py     -> đọc cấu hình, chọn provider
  tools.py      -> khai báo các "công cụ" agent được phép dùng
  providers.py  -> lớp "phiên dịch" giữa agent và từng nhà cung cấp LLM
  agent.py      -> ⭐ VÒNG LẶP AGENT (phần cốt lõi, không phụ thuộc provider)
"""

from .agent import Agent, AgentResult, Step

__all__ = ["Agent", "AgentResult", "Step"]
__version__ = "0.1.0"

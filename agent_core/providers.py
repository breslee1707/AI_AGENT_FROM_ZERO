"""Lớp "phiên dịch" giữa Agent và từng nhà cung cấp LLM (provider).

Vấn đề: Gemini, Claude (Anthropic), OpenAI đều hỗ trợ "function calling" (cho model
tự gọi tool), NHƯNG mỗi hãng có định dạng tin nhắn và cách khai báo tool khác nhau.

Giải pháp: định nghĩa MỘT giao diện chung `LLMClient` với đúng 1 việc — nhận lịch sử
hội thoại ở dạng CHUẨN HOÁ (trung lập) + danh sách tool, rồi trả về câu trả lời cũng
ở dạng chuẩn hoá. Nhờ vậy vòng lặp agent trong agent.py viết MỘT lần, không cần biết
đang nói chuyện với hãng nào. Mỗi client bên dưới chỉ lo "dịch xuôi/dịch ngược".

Định dạng LỊCH SỬ chuẩn hoá (list các dict) — dùng chung cho mọi provider:
  {"role": "user",      "content": "<chuỗi người dùng>"}
  {"role": "assistant", "content": "<chuỗi model, có thể rỗng>",
                        "tool_calls": [{"id","name","args"}, ...]}   # danh sách tool model muốn gọi
  {"role": "tool",      "id": "<id lượt gọi>", "name": "<tên tool>",
                        "content": "<kết quả tool trả về>"}

Nếu bạn mới học: hãy đọc kỹ GeminiClient (đường mặc định, đã kiểm thử). Hai client còn
lại (Anthropic, OpenAI) làm y hệt một ý tưởng, chỉ khác cú pháp của từng hãng.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .config import Settings
from .tools import ToolSpec


@dataclass
class NormalizedReply:
    """Câu trả lời của model sau khi đã CHUẨN HOÁ về dạng trung lập.

    - text: phần chữ model nói ra (có thể rỗng nếu nó chỉ muốn gọi tool).
    - tool_calls: danh sách tool model muốn gọi, mỗi cái gồm {id, name, args(dict)}.
      Nếu rỗng nghĩa là model đã trả lời xong, không cần gọi tool nữa.
    """

    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)


# ============================================================================
# GEMINI — đường mặc định, đã kiểm thử (dùng SDK chính thức google-genai)
# ============================================================================
class GeminiClient:
    def __init__(self, api_key: str, model: str, temperature: float):
        # Import trong __init__ để chỉ nạp SDK khi thật sự dùng provider này.
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def _to_contents(self, history: list[dict]):
        """Dịch lịch sử chuẩn hoá -> danh sách `Content` theo định dạng Gemini."""
        from google.genai import types

        contents = []
        for msg in history:
            role = msg["role"]
            if role == "user":
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=msg["content"])])
                )
            elif role == "assistant":
                # Lượt của model: role Gemini gọi là "model". Gồm phần chữ (nếu có)
                # cộng với các "function_call" mô tả tool nó muốn gọi.
                parts = []
                if msg.get("content"):
                    parts.append(types.Part.from_text(text=msg["content"]))
                for call in msg.get("tool_calls", []):
                    # Gemini đời mới YÊU CẦU gửi lại "thought_signature" (chữ ký suy nghĩ)
                    # đúng như lúc model sinh ra function_call; nếu thiếu sẽ báo lỗi 400.
                    # Vì thế ta dựng Part thủ công và đính kèm chữ ký đã lưu (xem complete()).
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                name=call["name"], args=call["args"]
                            ),
                            thought_signature=call.get("_signature"),
                        )
                    )
                contents.append(types.Content(role="model", parts=parts))
            elif role == "tool":
                # Trả kết quả tool về cho model. Gemini nhận nó trong một Content role
                # "user" với part kiểu function_response (đã kiểm chứng chạy đúng).
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=msg["name"], response={"result": msg["content"]}
                            )
                        ],
                    )
                )
        return contents

    def _to_tools(self, tools: list[ToolSpec]):
        """Dịch danh sách ToolSpec -> khai báo tool của Gemini."""
        from google.genai import types

        declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                # google-genai nhận thẳng JSON Schema qua 'parameters_json_schema' —
                # rất tiện, khỏi phải tự dựng lại đối tượng Schema.
                parameters_json_schema=t.parameters,
            )
            for t in tools
        ]
        return [types.Tool(function_declarations=declarations)]

    def complete(self, system: str, history: list[dict], tools: list[ToolSpec]) -> NormalizedReply:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=self._to_tools(tools),
            temperature=self._temperature,
            # TẮT "automatic function calling": mặc định SDK có thể tự gọi tool giúp
            # rồi giấu vòng lặp đi. Ta TẮT để tự viết vòng lặp trong agent.py — nhờ
            # vậy học viên NHÌN THẤY từng bước suy nghĩ -> gọi tool -> quan sát.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        response = self._client.models.generate_content(
            model=self._model, contents=self._to_contents(history), config=config
        )

        # Phân tích câu trả lời: gom phần chữ và các function_call model yêu cầu.
        text_parts, tool_calls = [], []
        candidates = response.candidates or []
        if candidates and candidates[0].content and candidates[0].content.parts:
            for i, part in enumerate(candidates[0].content.parts):
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    tool_calls.append({
                        # Gemini không kèm id cho lượt gọi -> ta tự sinh id để đồng bộ
                        # với các provider khác (Anthropic/OpenAI đều cần id).
                        "id": f"call_{i}",
                        "name": fc.name,
                        "args": dict(fc.args) if fc.args else {},
                        # Lưu "chữ ký suy nghĩ" của Gemini để lượt sau gửi trả lại đúng
                        # (các provider khác không có/không cần khoá này -> họ bỏ qua).
                        "_signature": part.thought_signature,
                    })
                elif getattr(part, "text", None):
                    text_parts.append(part.text)

        return NormalizedReply(text="".join(text_parts).strip(), tool_calls=tool_calls)


# ============================================================================
# ANTHROPIC (Claude) — cùng ý tưởng, khác cú pháp
# ============================================================================
class AnthropicClient:
    def __init__(self, api_key: str, model: str, max_tokens: int):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        # LƯU Ý: các model Claude đời mới (Opus 4.8...) KHÔNG nhận tham số 'temperature'
        # (gửi vào sẽ báo lỗi 400), nên client này CỐ Ý bỏ qua temperature.

    def _to_messages(self, history: list[dict]) -> list[dict]:
        """Dịch lịch sử chuẩn hoá -> mảng messages của Anthropic."""
        messages = []
        for msg in history:
            role = msg["role"]
            if role == "user":
                messages.append({"role": "user", "content": msg["content"]})
            elif role == "assistant":
                blocks = []
                if msg.get("content"):
                    blocks.append({"type": "text", "text": msg["content"]})
                for call in msg.get("tool_calls", []):
                    blocks.append({
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["name"],
                        "input": call["args"],
                    })
                messages.append({"role": "assistant", "content": blocks})
            elif role == "tool":
                # Kết quả tool đi trong một message role "user", block 'tool_result'.
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg["id"],
                        "content": msg["content"],
                    }],
                })
        return messages

    def _to_tools(self, tools: list[ToolSpec]) -> list[dict]:
        # Anthropic gọi JSON Schema của tham số là 'input_schema'.
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]

    def complete(self, system: str, history: list[dict], tools: list[ToolSpec]) -> NormalizedReply:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,                       # prompt hệ thống nằm ở tham số riêng
            tools=self._to_tools(tools),
            messages=self._to_messages(history),
        )

        # Câu trả lời là danh sách "block": có block text, có block tool_use.
        text_parts, tool_calls = [], []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "args": dict(block.input)})

        return NormalizedReply(text="".join(text_parts).strip(), tool_calls=tool_calls)


# ============================================================================
# OPENAI (Codex / GPT) — cùng ý tưởng, khác cú pháp
# ============================================================================
class OpenAIClient:
    def __init__(self, api_key: str, model: str, temperature: float, max_tokens: int):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def _to_messages(self, system: str, history: list[dict]) -> list[dict]:
        """Dịch lịch sử chuẩn hoá -> mảng messages của OpenAI (prompt hệ thống là 1 message)."""
        messages = [{"role": "system", "content": system}]
        for msg in history:
            role = msg["role"]
            if role == "user":
                messages.append({"role": "user", "content": msg["content"]})
            elif role == "assistant":
                m = {"role": "assistant", "content": msg.get("content") or None}
                if msg.get("tool_calls"):
                    # OpenAI để tham số tool dưới dạng CHUỖI JSON, nên ta json.dumps.
                    m["tool_calls"] = [{
                        "id": call["id"],
                        "type": "function",
                        "function": {"name": call["name"], "arguments": json.dumps(call["args"])},
                    } for call in msg["tool_calls"]]
                messages.append(m)
            elif role == "tool":
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg["id"],
                    "content": msg["content"],
                })
        return messages

    def _to_tools(self, tools: list[ToolSpec]) -> list[dict]:
        return [
            {"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters,
            }}
            for t in tools
        ]

    def complete(self, system: str, history: list[dict], tools: list[ToolSpec]) -> NormalizedReply:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            tools=self._to_tools(tools),
            messages=self._to_messages(system, history),
        )
        message = response.choices[0].message

        tool_calls = []
        for tc in (message.tool_calls or []):
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                # OpenAI trả tham số dạng chuỗi JSON -> json.loads về lại dict.
                "args": json.loads(tc.function.arguments or "{}"),
            })

        return NormalizedReply(text=(message.content or "").strip(), tool_calls=tool_calls)


# ============================================================================
# "Nhà máy" chọn client theo cấu hình — agent chỉ cần gọi build_client(settings)
# ============================================================================
def build_client(settings: Settings):
    """Trả về client phù hợp với provider đang chọn trong .env."""
    if settings.provider == "gemini":
        return GeminiClient(settings.gemini_api_key, settings.gemini_model, settings.temperature)
    if settings.provider == "anthropic":
        return AnthropicClient(settings.anthropic_api_key, settings.anthropic_model, settings.max_tokens)
    if settings.provider == "openai":
        return OpenAIClient(
            settings.openai_api_key, settings.openai_model, settings.temperature, settings.max_tokens
        )
    raise RuntimeError(f"Provider không hỗ trợ: {settings.provider}")

"""Khai báo các "công cụ" (tool) mà Agent được phép sử dụng.

Một tool gồm 4 phần, mô tả theo cách TRUNG LẬP (không dính tới provider nào):
  - name        : tên hàm, model gọi tool bằng tên này.
  - description : mô tả tool để model TỰ QUYẾT ĐỊNH khi nào nên gọi. Viết rõ, dễ hiểu.
  - parameters  : JSON Schema mô tả tham số đầu vào (kiểu, bắt buộc hay không).
  - func        : hàm Python thật sự chạy khi tool được gọi, trả về CHUỖI kết quả.

Vì sao chuẩn hoá kiểu này? Vì mỗi provider (Gemini/Claude/OpenAI) khai báo tool theo
định dạng khác nhau. Ta mô tả tool MỘT LẦN ở đây, rồi để mỗi "adapter" trong
providers.py tự dịch sang định dạng riêng của họ. Thêm tool mới = thêm 1 ToolSpec.

Bộ tool trong bài này được chọn để agent có thể PHỐI HỢP nhiều tool trong một câu hỏi:
  read_pdf (đọc số liệu) -> calculator (tính toán) -> convert_currency (đổi tiền tệ).
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class ToolSpec:
    """Mô tả trung lập của một tool (không phụ thuộc nhà cung cấp LLM)."""

    name: str
    description: str
    parameters: dict           # JSON Schema, ví dụ {"type": "object", "properties": {...}}
    func: Callable[..., str]   # hàm chạy thật, nhận **kwargs, trả về str


class ToolRegistry:
    """Sổ đăng ký tool: giữ danh sách tool và chịu trách nhiệm CHẠY chúng an toàn."""

    def __init__(self, specs: list[ToolSpec]):
        # Lưu theo dạng {tên: ToolSpec} để tra cứu nhanh khi model gọi tên tool.
        self._by_name = {s.name: s for s in specs}

    def specs(self) -> list[ToolSpec]:
        return list(self._by_name.values())

    def run(self, name: str, args: dict) -> str:
        """Chạy tool theo tên với tham số `args` (dict), luôn trả về CHUỖI.

        Ta bọc trong try/except: nếu tool lỗi (sai tham số, file không tồn tại...) thì
        trả lỗi về dưới dạng văn bản để AGENT ĐỌC ĐƯỢC và tự điều chỉnh, thay vì làm
        sập cả chương trình. Đây là nguyên tắc quan trọng khi cho model tự gọi tool.
        """
        spec = self._by_name.get(name)
        if spec is None:
            return f"[Lỗi] Không có tool tên '{name}'."
        try:
            return spec.func(**args)
        except Exception as e:  # noqa: BLE001 — cố ý bắt rộng để agent không bị sập
            return f"[Lỗi khi chạy tool '{name}']: {e}"


# ============================================================================
# TOOL 1 — CALCULATOR: máy tính an toàn cho biểu thức số học
# ============================================================================
# Vì sao KHÔNG dùng eval() của Python? Vì eval() chạy được MỌI câu lệnh Python
# (kể cả xoá file, gọi lệnh hệ thống) -> cực kỳ nguy hiểm khi đầu vào do model sinh.
# Thay vào đó ta phân tích biểu thức thành cây cú pháp (AST) và CHỈ cho phép các phép
# toán số học cơ bản. Đây là ví dụ tốt về "chỉ mở đúng thứ mình cần".

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,   # dấu âm, ví dụ -5
    ast.UAdd: operator.pos,   # dấu dương, ví dụ +5
}


def _eval_node(node):
    """Duyệt cây AST và chỉ tính các phép toán trong danh sách cho phép."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.operand))
    # Bất cứ thứ gì khác (tên biến, gọi hàm, chuỗi...) đều bị từ chối.
    raise ValueError("Biểu thức chứa thành phần không được phép.")


def calculator(expression: str) -> str:
    """TOOL: Tính một biểu thức số học (vd: '12000000 + 1200000')."""
    tree = ast.parse(expression, mode="eval")  # "eval" = biểu thức đơn, không phải câu lệnh
    value = _eval_node(tree.body)
    return f"{expression} = {value}"


# ============================================================================
# TOOL 2 — CONVERT_CURRENCY: quy đổi tiền tệ theo bảng tỷ giá cố định
# ============================================================================
# Vì sao dùng BẢNG TỶ GIÁ CỐ ĐỊNH thay vì gọi API tỷ giá thật?
#   - Để tool chạy được OFFLINE, không cần đăng ký API key -> học viên chạy được ngay.
#   - Mục tiêu bài này là dạy AGENT ĐIỀU PHỐI TOOL, không phải lấy tỷ giá chính xác.
#   Khi lên thực tế, chỉ cần thay hàm này bằng lời gọi API tỷ giá là xong.
#
# Quy ước: mỗi số là "bao nhiêu đơn vị tiền đó ĐỔI ĐƯỢC từ 1 USD" (rate so với USD).
# Muốn đổi A từ tiền X sang tiền Y: đưa A về USD (A / rate[X]) rồi nhân rate[Y].

_RATES_PER_USD = {
    "USD": 1.0,
    "VND": 25000.0,   # 1 USD ~ 25.000 đồng (số minh hoạ)
    "EUR": 0.92,
    "JPY": 155.0,
    "GBP": 0.79,
    "CNY": 7.2,
}


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """TOOL: Quy đổi `amount` từ đơn vị tiền này sang đơn vị tiền khác."""
    src = from_currency.strip().upper()
    dst = to_currency.strip().upper()

    if src not in _RATES_PER_USD or dst not in _RATES_PER_USD:
        ho_tro = ", ".join(_RATES_PER_USD.keys())
        return f"[Lỗi] Chỉ hỗ trợ các loại tiền: {ho_tro}."

    amount_in_usd = float(amount) / _RATES_PER_USD[src]
    result = amount_in_usd * _RATES_PER_USD[dst]
    # Làm tròn 2 chữ số cho gọn; định dạng có dấu phẩy ngăn cách hàng nghìn.
    return f"{amount:,.2f} {src} = {result:,.2f} {dst} (tỷ giá minh hoạ)"


# ============================================================================
# TOOL 3 — READ_PDF: đọc nội dung văn bản từ một file PDF
# ============================================================================
# Dùng pypdf. Ta GIỚI HẠN số ký tự trả về để không nhồi quá nhiều chữ vào ngữ cảnh
# của model (vừa tốn quota, vừa loãng thông tin).

def read_pdf(path: str, max_chars: int = 4000) -> str:
    """TOOL: Đọc và trả về phần đầu nội dung văn bản của một file PDF."""
    pdf_path = Path(path)
    if not pdf_path.exists():
        return f"[Lỗi] Không tìm thấy file: {path}"

    from pypdf import PdfReader  # import trong hàm: chỉ nạp khi thật sự đọc PDF

    reader = PdfReader(str(pdf_path))
    # Ghép chữ từ từng trang. Một số PDF (ảnh scan) có thể không trích được chữ.
    text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()

    if not text:
        return (
            f"Đã mở '{pdf_path.name}' ({len(reader.pages)} trang) nhưng không trích được "
            "chữ nào (có thể là PDF dạng ảnh scan)."
        )

    truncated = text[:max_chars]
    ghi_chu = "" if len(text) <= max_chars else f"\n\n...(đã cắt bớt, còn {len(text) - max_chars} ký tự)"
    return f"Nội dung '{pdf_path.name}' ({len(reader.pages)} trang):\n\n{truncated}{ghi_chu}"


# ============================================================================
# Lắp ráp toàn bộ tool thành một ToolRegistry cho agent
# ============================================================================

def build_default_registry() -> ToolRegistry:
    """Tạo bộ tool mặc định cho agent.

    Lưu ý cách khai báo `parameters` bằng JSON Schema: mô tả rõ từng tham số giúp model
    điền đúng. 'required' liệt kê tham số bắt buộc; tham số có mặc định thì không cần.
    """
    return ToolRegistry([
        ToolSpec(
            name="read_pdf",
            description=(
                "Đọc nội dung văn bản từ một file PDF theo đường dẫn. Dùng khi người "
                "dùng đưa đường dẫn tới file PDF và muốn tóm tắt / lấy số liệu / hỏi về "
                "nội dung của nó."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Đường dẫn tới file PDF trên máy.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Số ký tự tối đa lấy ra (mặc định 4000).",
                    },
                },
                "required": ["path"],
            },
            func=read_pdf,
        ),
        ToolSpec(
            name="calculator",
            description=(
                "Tính một biểu thức số học chính xác (cộng trừ nhân chia, luỹ thừa, "
                "phần dư). Dùng khi cần tính toán thay vì để model tự nhẩm (dễ sai)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Biểu thức số học, ví dụ: '12000000 + 1200000'.",
                    }
                },
                "required": ["expression"],
            },
            func=calculator,
        ),
        ToolSpec(
            name="convert_currency",
            description=(
                "Quy đổi một số tiền từ loại tiền này sang loại tiền khác "
                "(hỗ trợ USD, VND, EUR, JPY, GBP, CNY). Dùng khi người dùng muốn đổi "
                "ngoại tệ, ví dụ đổi tổng hoá đơn sang USD."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Số tiền cần quy đổi.",
                    },
                    "from_currency": {
                        "type": "string",
                        "description": "Mã tiền nguồn, ví dụ: VND.",
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "Mã tiền đích, ví dụ: USD.",
                    },
                },
                "required": ["amount", "from_currency", "to_currency"],
            },
            func=convert_currency,
        ),
    ])

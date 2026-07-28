"""Local PDF text extraction tool."""

from __future__ import annotations

from pathlib import Path

from .base import ToolSpec


def read_pdf(path: str, max_chars: int = 4000) -> str:
    """Extract the beginning of the text layer from a local PDF file."""
    pdf_path = Path(path)
    if not pdf_path.exists():
        return f"[Lỗi] Không tìm thấy file: {path}"

    from pypdf import PdfReader  # Load the optional dependency only when needed.

    reader = PdfReader(str(pdf_path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()

    if not text:
        return (
            f"Đã mở '{pdf_path.name}' ({len(reader.pages)} trang) nhưng không trích "
            "được chữ nào (có thể là PDF dạng ảnh scan)."
        )

    truncated = text[:max_chars]
    note = (
        ""
        if len(text) <= max_chars
        else f"\n\n...(đã cắt bớt, còn {len(text) - max_chars} ký tự)"
    )
    return (
        f"Nội dung '{pdf_path.name}' ({len(reader.pages)} trang):\n\n"
        f"{truncated}{note}"
    )


PDF_READER_TOOL = ToolSpec(
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
)

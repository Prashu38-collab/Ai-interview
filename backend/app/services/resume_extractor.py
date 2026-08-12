"""Extract plain text from an uploaded resume PDF."""

import io

from fastapi import HTTPException, status
from pypdf import PdfReader

MAX_PDF_BYTES = 5 * 1024 * 1024  # 5 MB


def extract_pdf_text(content: bytes) -> str:
    """Return the text of a PDF, raising a 422 for unreadable / empty files."""
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded file is empty.",
        )
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The PDF is too large (max 5 MB).",
        )
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only PDF resumes are supported.",
        )
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pypdf raises various errors for corrupt files
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Could not read the PDF. It may be corrupted or password-protected.",
        ) from exc
    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No text could be extracted. Scanned-image PDFs are not supported yet.",
        )
    return text

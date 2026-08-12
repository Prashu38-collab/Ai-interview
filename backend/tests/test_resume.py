"""Tests for the PDF resume extraction endpoint."""

import io

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def _make_pdf(text: str) -> bytes:
    """Build a tiny single-page PDF that contains ``text``."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = stream
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _extract(client, data: bytes, filename: str = "resume.pdf"):
    return client.post(
        "/resume/extract",
        files={"file": (filename, data, "application/pdf")},
    )


def test_extract_pdf_returns_text(client):
    pdf = _make_pdf("Python FastAPI PostgreSQL resume")
    res = _extract(client, pdf)
    assert res.status_code == 200
    body = res.json()
    assert body["filename"] == "resume.pdf"
    assert "Python FastAPI PostgreSQL resume" in body["text"]


def test_extract_rejects_non_pdf(client):
    res = _extract(client, b"%PDF fake body", filename="notes.txt")
    assert res.status_code == 422
    assert "PDF" in res.json()["detail"]


def test_extract_rejects_empty_file(client):
    res = _extract(client, b"", filename="empty.pdf")
    assert res.status_code == 422
    assert "empty" in res.json()["detail"].lower()


def test_extract_rejects_corrupt_pdf(client):
    res = _extract(client, b"%PDF-1.4\nthis is not a real pdf structure")
    assert res.status_code == 422


def test_extract_rejects_oversized_pdf(client):
    big = b"%PDF" + b"\x00" * (6 * 1024 * 1024)
    res = _extract(client, big)
    assert res.status_code == 422
    assert "large" in res.json()["detail"].lower()


def test_extract_rejects_pdf_without_text(client):
    pdf = _make_pdf("   ")
    res = _extract(client, pdf)
    assert res.status_code == 422

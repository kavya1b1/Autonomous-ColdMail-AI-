"""PDF text extraction utilities (shared by API routes and agent nodes).

Uses PyMuPDF (fitz), which is already a declared project dependency and is
the same library used by agents/nodes/parse.py — avoids introducing a new
dependency (PyPDF2) that was referenced but never installed.
"""
import fitz  # PyMuPDF


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from raw PDF bytes (e.g. an uploaded file)."""
    try:
        text = ""
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text.strip()
    except Exception as e:
        return f"[Error reading PDF: {str(e)}]"


def extract_text_from_pdf_path(path: str) -> str:
    """Extract text from a PDF file on disk."""
    try:
        text = ""
        with fitz.open(path) as doc:
            for page in doc:
                text += page.get_text()
        return text.strip()
    except Exception as e:
        return f"[Error reading PDF: {str(e)}]"

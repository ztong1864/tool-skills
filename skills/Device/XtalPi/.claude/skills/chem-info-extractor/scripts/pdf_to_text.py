import os
import sys
from typing import List

from PyPDF2 import PdfReader


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_text(path: str, text: str) -> None:
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _safe_page_text(page) -> str:
    text = page.extract_text() or ""
    text = text.replace("\x00", "")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


def pdf_to_text(pdf_path: str, text_dir: str, *, force: bool = False) -> List[str]:
    _ensure_dir(text_dir)
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    if not force and os.path.isdir(text_dir):
        cached = [
            os.path.join(text_dir, fname)
            for fname in sorted(os.listdir(text_dir))
            if fname.lower().endswith(".txt")
            and "_page_" in fname.lower()
            and os.path.getsize(os.path.join(text_dir, fname)) > 0
        ]
        if cached:
            return cached

    reader = PdfReader(pdf_path)
    out_paths: List[str] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = _safe_page_text(page)
        if not text:
            continue
        out_path = os.path.join(text_dir, f"{pdf_name}_page_{page_index:03d}.txt")
        _write_text(out_path, text)
        out_paths.append(out_path)
    return out_paths


def pdf_to_text_pages(pdf_path: str, text_dir: str, *, force: bool = False) -> List[str]:
    return pdf_to_text(pdf_path, text_dir, force=force)


def _list_pdfs(pdf_dir: str) -> List[str]:
    return [
        os.path.join(pdf_dir, f)
        for f in sorted(os.listdir(pdf_dir))
        if f.lower().endswith(".pdf")
    ]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m pdf_to_text <pdf_dir|pdf_path> <output_dir>")
    input_path = sys.argv[1]
    output_dir = sys.argv[2]

    if os.path.isdir(input_path):
        for pdf_path in _list_pdfs(input_path):
            pdf_id = os.path.splitext(os.path.basename(pdf_path))[0]
            pages = pdf_to_text(pdf_path, os.path.join(output_dir, pdf_id))
            print(f"{pdf_id}: extracted_pages={len(pages)}")
        return

    pages = pdf_to_text(input_path, output_dir)
    print(f"extracted_pages={len(pages)}")


if __name__ == "__main__":
    main()

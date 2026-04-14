"""
Rich PDF text extraction with table and image support.

Uses PyMuPDF (fitz) to extract:
- Text content (all pages)
- Tables → formatted as markdown tables
- Images → described with dimensions and page location

This module is used by:
- backend/routers/files.py  (upload-time extraction for frontend textarea)
- backend/routers/rfp.py    (stage-time context building for LLM)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum extracted text length (chars).  GPT-4.1 has a 1M-token context
# window, so 500 KB of text (~125K tokens) is safe.
MAX_EXTRACT_CHARS = 512_000


def extract_pdf_content(pdf_path: str, *, max_chars: int = MAX_EXTRACT_CHARS) -> Optional[str]:
    """Extract text, tables, and image descriptions from a PDF file.

    Returns a single markdown string with the full document content,
    or None if extraction fails or the PDF has no usable content.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed — cannot extract PDF content")
        return None

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        logger.warning("Failed to open PDF %s: %s", pdf_path, exc)
        return None

    parts: list[str] = []
    total_len = 0
    num_pages = len(doc)

    for page_idx, page in enumerate(doc):
        if total_len >= max_chars:
            parts.append(f"\n\n[... Truncated at {max_chars:,} characters — "
                         f"{num_pages - page_idx} remaining pages omitted ...]\n")
            break

        page_parts: list[str] = []
        page_num = page_idx + 1
        page_parts.append(f"\n--- Page {page_num} of {num_pages} ---\n")

        # ─── Tables ──────────────────────────────────────────────────
        # Extract tables FIRST so we can mark their bounding boxes and
        # avoid duplicating table text in the plain-text pass.
        table_rects: list = []
        try:
            tables = page.find_tables()
            for tbl_idx, table in enumerate(tables.tables):
                table_rects.append(table.bbox)
                md_table = _table_to_markdown(table)
                if md_table:
                    page_parts.append(f"\n**[Table {tbl_idx + 1} on page {page_num}]**\n")
                    page_parts.append(md_table)
                    page_parts.append("")
        except Exception:
            # find_tables() can fail on unusual page layouts
            pass

        # ─── Text ────────────────────────────────────────────────────
        # Use block-level extraction to get text while skipping blocks
        # that overlap with already-extracted tables.
        try:
            blocks = page.get_text("blocks")  # list of (x0,y0,x1,y1,text,block_no,block_type)
            for block in blocks:
                # block_type 0 = text, 1 = image
                if block[6] == 0:  # text block
                    block_rect = fitz.Rect(block[:4])
                    # Skip if this text block overlaps significantly with a table
                    if _overlaps_any(block_rect, table_rects):
                        continue
                    text = block[4].strip()
                    if text:
                        page_parts.append(text)
        except Exception:
            # Fallback: plain text extraction
            try:
                text = page.get_text().strip()
                if text:
                    page_parts.append(text)
            except Exception:
                pass

        # ─── Images ──────────────────────────────────────────────────
        try:
            images = page.get_images(full=True)
            for img_idx, img_info in enumerate(images):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image:
                        w = base_image.get("width", 0)
                        h = base_image.get("height", 0)
                        img_ext = base_image.get("ext", "unknown")
                        size_bytes = len(base_image.get("image", b""))
                        size_str = (f"{size_bytes}" if size_bytes < 1024
                                    else f"{size_bytes/1024:.1f}KB"
                                    if size_bytes < 1024*1024
                                    else f"{size_bytes/1024/1024:.1f}MB")
                        page_parts.append(
                            f"\n**[Image {img_idx + 1} on page {page_num}: "
                            f"{w}x{h}px, {img_ext}, {size_str}]** "
                            f"*(This image may contain a chart, diagram, or figure "
                            f"relevant to the RFP requirements.)*\n"
                        )
                except Exception:
                    page_parts.append(
                        f"\n**[Image {img_idx + 1} on page {page_num}]** "
                        f"*(Embedded image — could not extract details.)*\n"
                    )
        except Exception:
            pass

        page_text = "\n".join(page_parts)
        parts.append(page_text)
        total_len += len(page_text)

    doc.close()

    result = "\n".join(parts).strip()
    if not result:
        return None

    # Final length cap
    if len(result) > max_chars:
        result = result[:max_chars]

    return result


def _table_to_markdown(table) -> Optional[str]:
    """Convert a PyMuPDF Table object to a markdown table string."""
    try:
        data = table.extract()
        if not data or len(data) < 1:
            return None

        # Clean cells: replace None with empty string, strip whitespace
        rows = []
        for row in data:
            rows.append([_clean_cell(cell) for cell in row])

        if not rows:
            return None

        # Build markdown table
        num_cols = max(len(r) for r in rows)
        # Pad short rows
        for row in rows:
            while len(row) < num_cols:
                row.append("")

        lines = []
        # Header row
        lines.append("| " + " | ".join(rows[0]) + " |")
        # Separator
        lines.append("| " + " | ".join(["---"] * num_cols) + " |")
        # Data rows
        for row in rows[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)
    except Exception:
        return None


def _clean_cell(cell) -> str:
    """Clean a table cell value for markdown output."""
    if cell is None:
        return ""
    text = str(cell).strip()
    # Replace newlines within cells (common in multi-line cells)
    text = text.replace("\n", " ")
    # Escape pipe characters that would break markdown table
    text = text.replace("|", "\\|")
    return text


def _overlaps_any(block_rect, table_rects, threshold: float = 0.5) -> bool:
    """Check if a text block rectangle overlaps significantly with any table."""
    import fitz
    for tbl_bbox in table_rects:
        tbl_rect = fitz.Rect(tbl_bbox)
        intersection = block_rect & tbl_rect
        if intersection.is_empty:
            continue
        block_area = block_rect.width * block_rect.height
        if block_area <= 0:
            continue
        overlap_ratio = (intersection.width * intersection.height) / block_area
        if overlap_ratio >= threshold:
            return True
    return False

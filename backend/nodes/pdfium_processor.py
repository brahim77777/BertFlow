from __future__ import annotations

import os
from typing import Any

from backend.core.registry import register_node
# Import the thin wrapper that exposes rag_rust functionalities
import backend.infrastructure.rust_bridge as rust_bridge 


@register_node
class PDFiumProcessor:
    node_type = "pdfium_processor"
    label = "Upload PDF (PDFium)"
    description = "Extracts text page-by-page from multiple PDFs using an optimized, multi-threaded Rust PDFium backend."
    category = "io"
    version = "1.1.0"
    ui_config = {"icon": "file-text", "color": "#10B981", "category_order": 3}

    inputs = {}

    outputs = {
        "pages": {"type": "array"},           # Per-page extracted text
        "page_sources": {"type": "array"},     # Source filename per page
        "page_numbers": {"type": "array"},     # 1-indexed page number per page
        "text": {"type": "string"},            # Unified string
        "filenames": {"type": "array"},        # Unique filenames list
        "metadata": {"type": "json"},
    }

    args_schema = {
        "files": {"type": "file", "default": "", "description": "Select a PDF file"},
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        raw_files = args.get("files", "")
        if not raw_files.strip():
            return {
                "pages": [],
                "page_sources": [],
                "page_numbers": [],
                "text": "",
                "filenames": [],
                "metadata": {"error": "No file configurations provided"},
            }

        # Process a single item or an array/comma-separated cluster of target documents
        file_targets = [f.strip() for f in raw_files.split(",") if f.strip()]
        resolved_paths = []
        missing_files = []

        for file_path in file_targets:
            candidates = [
                file_path,
                os.path.join("files", file_path),
                os.path.join(os.path.dirname(__file__), "..", "..", "files", file_path),
            ]

            resolved = None
            for c in candidates:
                if os.path.isfile(c):
                    resolved = c
                    break

            if resolved:
                resolved_paths.append(resolved)
            else:
                missing_files.append(file_path)

        if missing_files:
            return {
                "pages": [],
                "page_sources": [],
                "page_numbers": [],
                "text": "",
                "filenames": file_targets,
                "metadata": {"error": f"Could not find files: {', '.join(missing_files)}"},
            }

        try:
            # Process each file individually to track per-page source and page number.
            # This mirrors the reference pipeline in indexing_service.py.
            all_pages = []
            page_sources = []
            page_numbers = []

            for resolved_path in resolved_paths:
                filename = os.path.basename(resolved_path)
                file_pages = rust_bridge.load_pdf_pages_pdfium_many([resolved_path])
                for page_idx, page_text in enumerate(file_pages, start=1):
                    all_pages.append(page_text)
                    page_sources.append(filename)
                    page_numbers.append(page_idx)

            # Combine individual elements for basic single-string consumption models
            unified_text = "\n\n--- Page Break ---\n\n".join(all_pages)

            return {
                "pages": all_pages,
                "page_sources": page_sources,
                "page_numbers": page_numbers,
                "text": unified_text,
                "filenames": [os.path.basename(p) for p in resolved_paths],
                "metadata": {
                    "total_pages_extracted": len(all_pages),
                    "total_characters": len(unified_text),
                    "files_processed": len(resolved_paths),
                    "error": None,
                },
            }
        except Exception as e:
            return {
                "pages": [],
                "page_sources": [],
                "page_numbers": [],
                "text": "",
                "filenames": file_targets,
                "metadata": {"error": f"Rust Bridge Execution Failure: {str(e)}"},
            }
from __future__ import annotations

import asyncio
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
        "pages": {"type": "array"},
    }

    args_schema = {
        "files": {"type": "file", "default": "", "description": "Select a PDF file"},
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        raw_files = args.get("files", "")
        if not raw_files.strip():
            return {"pages": []}

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
            return {"pages": []}

        def _extract() -> list[dict]:
            pages = []
            for resolved_path in resolved_paths:
                filename = os.path.basename(resolved_path)
                file_pages = rust_bridge.load_pdf_pages_pdfium_many([resolved_path])
                for page_idx, page_text in enumerate(file_pages, start=1):
                    pages.append({
                        "text": page_text,
                        "source": filename,
                        "page": page_idx,
                    })
            return pages

        try:
            # PDFium extraction is blocking and CPU-bound — run it off the
            # event loop so it doesn't stall other concurrently-running nodes.
            all_pages = await asyncio.to_thread(_extract)
            return {"pages": all_pages}
        except Exception as e:
            raise RuntimeError(f"Rust Bridge Execution Failure: {e}")
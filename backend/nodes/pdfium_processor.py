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
    version = "1.0.0"
    ui_config = {"icon": "file-text", "color": "#10B981", "category_order": 3}

    inputs = {}

    outputs = {
        "pages": {"type": "array"},  # Returns individual extracted text fragments per page
        "text": {"type": "string"},  # Unified string joined by standard line breaks
        "filenames": {"type": "array"},
        "metadata": {"type": "json"},
    }

    args_schema = {
        # "files": {"type": "string", "ui_type": "file", "default": "", "description": "Select a PDF file"},
        "files": {"type": "file", "default": "", "description": "Select a PDF file"},
    }

    @staticmethod
    async def run(args: dict, inputs: dict, context: Any) -> dict:
        raw_files = args.get("files", "")
        if not raw_files.strip():
            return {
                "pages": [],
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
                "text": "",
                "filenames": file_targets,
                "metadata": {"error": f"Could not find files: {', '.join(missing_files)}"},
            }

        try:
            # Invoking your optimized parallel implementation across the target paths
            # This calls out to load_pdf_pages_pdfium_many_impl inside pdf_ops.rs via PyO3
            extracted_pages = rust_bridge.load_pdf_pages_pdfium_many(resolved_paths)
            
            # Combine individual elements for basic single-string consumption models
            unified_text = "\n\n--- Page Break ---\n\n".join(extracted_pages)

            return {
                "pages": extracted_pages,
                "text": unified_text,
                "filenames": [os.path.basename(p) for p in resolved_paths],
                "metadata": {
                    "total_pages_extracted": len(extracted_pages),
                    "total_characters": len(unified_text),
                    "error": None,
                },
            }
        except Exception as e:
            return {
                "pages": [],
                "text": "",
                "filenames": file_targets,
                "metadata": {"error": f"Rust Bridge Execution Failure: {str(e)}"},
            }
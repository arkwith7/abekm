"""
Presentation File Manager - handles storage paths for generated assets
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from app.core.config import settings


class PresentationFileManager:
    """Manage storage of HTML and PPTX presentation files."""

    def __init__(self) -> None:
        base_path = Path(settings.presentation_output_dir)
        if not base_path.is_absolute():
            base_root = Path(__file__).resolve().parents[2]  # backend/
            base_path = (base_root / base_path).resolve()
        self.base_path = base_path
        self.html_dir = self.base_path / "html"
        self.pptx_dir = self.base_path / "pptx"
        self.outline_dir = self.base_path / "outline"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.html_dir.mkdir(parents=True, exist_ok=True)
        self.pptx_dir.mkdir(parents=True, exist_ok=True)
        self.outline_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slugify(value: str, default: str = "presentation") -> str:
        trimmed = value.strip().lower() if value else default
        safe_chars = [c if c.isalnum() else "-" for c in trimmed]
        slug = "".join(safe_chars)
        slug = slug.strip("-") or default
        return slug[:80]

    def _build_filename(self, prefix: str, extension: str) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        short_id = uuid.uuid4().hex[:8]
        return f"{prefix}_{timestamp}_{short_id}.{extension}"

    def save_html(self, content: str, title: Optional[str] = None) -> Path:
        """Save HTML content and return file path."""
        slug = self._slugify(title or "presentation")
        filename = self._build_filename(slug, "html")
        path = self.html_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def save_outline(self, outline_json: str, title: Optional[str] = None) -> Path:
        """Save outline JSON content and return file path."""
        slug = self._slugify(title or "presentation")
        filename = self._build_filename(slug, "json")
        path = self.outline_dir / filename
        path.write_text(outline_json, encoding="utf-8")
        return path

    def save_pptx(self, data: bytes, title: Optional[str] = None) -> Path:
        """Save PPTX binary content and return file path."""
        slug = self._slugify(title or "presentation")
        filename = self._build_filename(slug, "pptx")
        path = self.pptx_dir / filename
        path.write_bytes(data)
        return path

    def resolve_file(self, filename: str, file_type: Literal["html", "pptx", "outline"]) -> Path:
        if file_type == "html":
            directory = self.html_dir
        elif file_type == "pptx":
            directory = self.pptx_dir
        else:
            directory = self.outline_dir
        path = directory / filename
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return path

    def delete_file(self, filename: str, file_type: Literal["html", "pptx", "outline"]) -> None:
        path = self.resolve_file(filename, file_type)
        path.unlink(missing_ok=True)


file_manager = PresentationFileManager()

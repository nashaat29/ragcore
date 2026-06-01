from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ragcore.core.config import settings
from ragcore.core.exceptions import IndexNotFoundError
from ragcore.core.logger import get_logger
from ragcore.vectorstore.faiss_store import FAISSVectorStore

logger = get_logger("ragcore.vectorstore.index_manager")


class IndexManager:
    def __init__(self, base_dir: str | Path | None = None):
        self._base_dir = Path(base_dir or settings.data_path / "indexes")
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._registry_file = self._base_dir / "registry.json"
        self._registry: dict[str, dict[str, Any]] = self._load_registry()

    def _load_registry(self) -> dict[str, dict[str, Any]]:
        if self._registry_file.exists():
            try:
                with open(self._registry_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_registry(self) -> None:
        with open(self._registry_file, "w") as f:
            json.dump(self._registry, f, indent=2, default=str)

    def list_indexes(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "created_at": meta.get("created_at"),
                "updated_at": meta.get("updated_at"),
                "vector_count": meta.get("vector_count", 0),
                "dimension": meta.get("dimension", 0),
                "size_bytes": meta.get("size_bytes", 0),
                "active": meta.get("active", False),
            }
            for name, meta in self._registry.items()
        ]

    def _validate_name(self, name: str) -> None:
        if not re.match(r'^[\w\-]+$', name):
            raise ValueError(f"Invalid index name '{name}'. Use only letters, digits, underscores, and hyphens.")

    def save_index(self, name: str, vectorstore: FAISSVectorStore) -> Path:
        self._validate_name(name)
        index_dir = self._base_dir / name
        vectorstore.save(index_dir)

        stats = vectorstore.get_stats()
        now = datetime.utcnow().isoformat()

        for existing_name, meta in self._registry.items():
            meta["active"] = False

        self._registry[name] = {
            "created_at": self._registry.get(name, {}).get("created_at", now),
            "updated_at": now,
            "vector_count": stats["total_vectors"],
            "dimension": stats["dimension"],
            "size_bytes": self._dir_size(index_dir),
            "active": True,
        }
        self._save_registry()
        logger.info(f"Index '{name}' saved and set as active")
        return index_dir

    def load_index(self, name: str, vectorstore: FAISSVectorStore) -> None:
        self._validate_name(name)
        index_dir = self._base_dir / name
        if not index_dir.exists():
            raise IndexNotFoundError(f"Index '{name}' not found at {index_dir}")
        vectorstore.load(index_dir)
        logger.info(f"Index '{name}' loaded ({vectorstore.size} vectors)")

    def load_active_index(self, vectorstore: FAISSVectorStore) -> bool:
        for name, meta in self._registry.items():
            if meta.get("active"):
                self.load_index(name, vectorstore)
                return True
        return False

    def delete_index(self, name: str) -> None:
        index_dir = self._base_dir / name
        if index_dir.exists():
            shutil.rmtree(index_dir)
        self._registry.pop(name, None)
        self._save_registry()
        logger.info(f"Index '{name}' deleted")

    def get_active_index_name(self) -> str | None:
        for name, meta in self._registry.items():
            if meta.get("active"):
                return name
        return None

    def set_active_index(self, name: str) -> None:
        index_dir = self._base_dir / name
        if not index_dir.exists():
            raise IndexNotFoundError(f"Index '{name}' does not exist")
        for existing_name, meta in self._registry.items():
            meta["active"] = existing_name == name
        self._save_registry()
        logger.info(f"Index '{name}' set as active")

    def _dir_size(self, path: Path) -> int:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

    @property
    def base_dir(self) -> Path:
        return self._base_dir

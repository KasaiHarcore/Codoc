from __future__ import annotations

import os
import traceback
from collections.abc import Iterable
from typing import Any

from loguru import logger
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS

from app.globals import EXCLUDE_DIRS, EXCLUDE_FILES, LOADER_MAPPING


ROOT_DIR: str = ""


def set_root_dir(path: str) -> None:
    global ROOT_DIR
    ROOT_DIR = os.path.abspath(path)


def get_root_dir() -> str:
    return ROOT_DIR


def _iter_candidate_files(root_dir: str) -> Iterable[str]:
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(path, root_dir)
            if any(rel_path.endswith(exclude_file) for exclude_file in EXCLUDE_FILES):
                continue
            yield path


def load_files(root_dir: str | None = None):
    """Load documents under the root folder using the app's LOADER_MAPPING."""
    root_dir = os.path.abspath(root_dir or ROOT_DIR)
    if not root_dir or not os.path.isdir(root_dir):
        raise ValueError(f"Invalid ROOT_DIR: {root_dir!r}")

    documents = []
    for path in _iter_candidate_files(root_dir):
        for ext, entry in LOADER_MAPPING.items():
            if not path.endswith(ext):
                continue
            loader_cls = entry["loader"]
            loader_kwargs: dict[str, Any] = entry.get("args") or {}
            try:
                try:
                    loader = loader_cls(path, **loader_kwargs)
                except ModuleNotFoundError as e:
                    # Optional loader dependency missing (e.g. 'unstructured').
                    # Fall back to plain text to keep indexing functional.
                    logger.warning(
                        f"RAG: loader dependency missing for {path} ({loader_cls.__name__}): {e}. Falling back to TextLoader."
                    )
                    loader = TextLoader(path, encoding="utf-8", autodetect_encoding=True)
                documents.extend(loader.load())
            except Exception as e:
                logger.warning(f"RAG: failed to load {path}: {e}")
                logger.debug(traceback.format_exc())
            break
    return documents


def get_local_vector_store(embeddings, path: str) -> FAISS | None:
    """Load a FAISS store if it exists; otherwise return None."""
    try:
        return FAISS.load_local(path, embeddings)  # older langchain
    except TypeError:
        try:
            return FAISS.load_local(
                path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
        except Exception:
            return None
    except Exception:
        return None

"""
Build the Chroma vector database from the master JSONL dataset.

Usage:
    python src/vector_db/create_vector_db.py
"""

import json
import os
import logging
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

logger = logging.getLogger("SymptoGuide")

# -------- Settings --------
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]

MASTER_FILE = PROJECT_ROOT / "data" / "processed" / "symptoguide_master.jsonl"
DB_DIR = str(PROJECT_ROOT / "chroma_db")
EMBED_MODEL = "BAAI/bge-large-en-v1.5"


def load_documents(jsonl_path: Path) -> list[Document]:
    """Load JSONL records and convert them to LangChain Documents."""
    docs = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)

            # Use embedding_context if available, otherwise fall back to text
            content = entry.get("embedding_context") or entry.get("text", "")
            metadata = {
                "entity_type": entry.get("entity_type", "unknown"),
                "name": entry.get("name", "Unknown"),
                "url": entry.get("url", ""),
                "source": entry.get("source", ""),
            }
            docs.append(Document(page_content=content, metadata=metadata))
    return docs


def build_vector_db(docs: list[Document], persist_dir: str, model_name: str) -> None:
    """Create and persist a Chroma vector database from the given documents."""
    logger.info(f"Loading embedding model: {model_name}")
    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    logger.info(f"Building vector database with {len(docs)} documents...")

    # Remove old DB if it exists
    if os.path.exists(persist_dir):
        import shutil
        shutil.rmtree(persist_dir)
        logger.info("Removed old vector database.")

    Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_dir,
    )

    logger.info(f"Vector database saved to: {persist_dir}")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if not MASTER_FILE.exists():
        logger.error(f"Master dataset not found: {MASTER_FILE}")
        logger.error("Run the processing pipeline first (create_master_dataset.py).")
        return

    docs = load_documents(MASTER_FILE)
    logger.info(f"Loaded {len(docs)} documents from {MASTER_FILE}")

    if not docs:
        logger.error("No documents loaded. Aborting.")
        return

    build_vector_db(docs, DB_DIR, EMBED_MODEL)
    logger.info("Vector database creation complete!")


if __name__ == "__main__":
    main()

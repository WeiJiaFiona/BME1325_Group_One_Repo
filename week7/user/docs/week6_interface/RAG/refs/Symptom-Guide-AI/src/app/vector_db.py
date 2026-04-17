"""
Vector database utilities: loading and smart search.
"""

import os
import logging
from typing import List

import streamlit as st
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from src.app.config import MedicalConfig

logger = logging.getLogger("SymptoGuide")


@st.cache_resource
def load_vector_db():
    """
    Load the Chroma vector database with embeddings.
    Cached to avoid reloading on every interaction.
    """
    config = MedicalConfig()
    
    if not os.path.exists(config.DB_DIR):
        st.error(f"❌ Database not found at {config.DB_DIR}")
        st.stop()
    
    logger.info("Loading Vector Database...")
    
    # Load embeddings
    embeddings = HuggingFaceEmbeddings(
        model_name=config.EMBED_MODEL,
        model_kwargs={'device': 'cpu', 'local_files_only': True},
        encode_kwargs={'normalize_embeddings': True}
    )
    
    # Load Chroma DB
    vector_db = Chroma(
        persist_directory=config.DB_DIR,
        embedding_function=embeddings
    )
    
    logger.info("Vector Database Loaded Successfully.")
    return vector_db


def smart_category_search(vector_db, query: str) -> List:
    """
    Smart search: attempt to retrieve several documents across key categories
    and return tuples of (Document, score).  Each score comes directly from
    the Chroma `similarity_search_with_score` API, allowing callers to compute
    a rough confidence level.  If category-specific results are not found,
    fall back to a generic search.

    Documents with a distance score above MAX_DISTANCE_THRESHOLD are discarded
    to prevent irrelevant results (e.g., Q fever for a headache query) from
    being injected into the LLM context.
    """
    MAX_DISTANCE_THRESHOLD = 1.2  # lower = stricter; filters out irrelevant results

    results = []
    seen_ids = set()
    
    targets = [
        {"type": "condition", "k": 3},
        {"type": "symptom_guide", "k": 2},
        {"type": "test", "k": 2}
    ]
    
    logger.info(f"Smart Search Query: '{query}'")
    
    # Try category-specific searches
    for target in targets:
        try:
            docs_with_score = vector_db.similarity_search_with_score(
                query,
                k=target["k"],
                filter={"entity_type": target["type"]}
            )
            for doc, score in docs_with_score:
                # Filter out low-relevance results
                if score > MAX_DISTANCE_THRESHOLD:
                    logger.info(f"Filtered out [{target['type']}]: {doc.metadata.get('name', 'Unknown')} (score={score:.2f} > {MAX_DISTANCE_THRESHOLD})")
                    continue

                doc_id = doc.metadata.get('url', doc.page_content[:20])
                if doc_id not in seen_ids:
                    doc.metadata['search_category'] = target['type'].upper()
                    results.append((doc, score))
                    seen_ids.add(doc_id)
                    logger.info(f"Found [{target['type']}]: {doc.metadata.get('name', 'Unknown')} (score={score:.2f})")
        except Exception as e:
            logger.warning(f"Category search failed for {target['type']}: {e}")
            continue
    
    # Fallback: generic search if no results
    if not results:
        logger.info("No category matches. Falling back to generic search.")
        generic_results = vector_db.similarity_search_with_score(query, k=4)
        # Apply threshold to fallback results too
        results = [(doc, score) for doc, score in generic_results if score <= MAX_DISTANCE_THRESHOLD]
    
    return results


def list_symptom_names(vector_db) -> list:
    """
    Return a sorted list of unique symptom names available in the database.
    This is used for UI dropdowns to give users a controlled vocabulary.
    """
    names = set()
    try:
        data = vector_db._collection.get()
        metadatas = data.get('metadatas', [])
        for m in metadatas:
            if m.get('entity_type') == 'symptom_guide':
                name = m.get('name')
                if name:
                    names.add(name)
    except Exception:
        # if anything fails, fall back to empty list
        return []
    return sorted(names)

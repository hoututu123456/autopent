import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.rag_engine import RAGEngine


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Initializing AutoPentestAI Knowledge Base (RAG)...")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_dirs = [
        os.path.join(base_dir, "data", "knowledge"),
        os.path.join(base_dir, "data", "skills"),
        os.path.join(base_dir, "data", "vulndb"),
        os.path.join(base_dir, "data", "playbooks"),
        os.path.join(base_dir, "data", "external", "defense"),
    ]

    rag = RAGEngine(
        persist_directory=os.path.join(base_dir, "data", "vector_db"),
        cache_directory=os.path.join(base_dir, "data", "models"),
    )
    try:
        if not rag.initialize():
            logger.error("Failed to initialize RAG Engine.")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Critical error during RAG initialization: {e}")
        sys.exit(1)

    total_files = 0
    for d in base_dirs:
        if os.path.exists(d):
            for root, _, files in os.walk(d):
                total_files += len([f for f in files if f.endswith(".md")])

    logger.info(f"Found {total_files} documents to index.")

    for d in base_dirs:
        if os.path.exists(d):
            logger.info(f"Indexing directory: {d}")
            rag.index_directory(d)
        else:
            logger.warning(f"Directory not found (skipping): {d}")

    logger.info("Knowledge Base initialization complete!")
    logger.info(f"Vector Database stored in: {rag.persist_directory}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()

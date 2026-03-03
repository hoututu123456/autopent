import argparse
import json
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.utils.rag_engine import RAGEngine
from src.utils.web_searcher import WebSearcher


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="kali linux web pentest cookbook")
    ap.add_argument("--search-results", type=int, default=3)
    ap.add_argument("--rag-results", type=int, default=3)
    ap.add_argument("--engine", default="auto", choices=["auto", "bing", "ddg"])
    args = ap.parse_args()

    results, meta = WebSearcher.search_with_meta(args.query, args.search_results, preferred_engine=args.engine)
    print("== web_search ==")
    print(json.dumps({"meta": meta, "count": len(results), "top": results[:3]}, ensure_ascii=False, indent=2))

    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    rag = RAGEngine(
        persist_directory=os.path.join(base, "data", "vector_db"),
        cache_directory=os.path.join(base, "data", "models"),
    )
    dirs = [
        os.path.join(base, "data", "knowledge"),
        os.path.join(base, "data", "skills"),
        os.path.join(base, "data", "vulndb"),
        os.path.join(base, "data", "playbooks"),
    ]
    hybrid = rag.hybrid_query(args.query, n_results=args.rag_results, directories=dirs)
    print("== hybrid_rag ==")
    print(json.dumps({"count": len(hybrid), "top": hybrid[:3]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

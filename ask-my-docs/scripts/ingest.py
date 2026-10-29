#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline import RAGPipeline

def main():
    parser = argparse.ArgumentParser(description="Ingest documents into the RAG pipeline.")
    parser.add_argument("--docs-dir", type=str, default="./docs", help="Directory containing documents to ingest")
    args = parser.parse_args()
    
    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        print(f"Error: Directory {docs_dir} does not exist.")
        sys.exit(1)
        
    print(f"Initializing pipeline and starting ingestion from {docs_dir}...")
    pipeline = RAGPipeline()
    stats = pipeline.ingest(docs_dir)
    
    print("\n" + "="*40)
    print("INGESTION COMPLETE")
    print("="*40)
    print(f"Files processed : {stats.get('num_files', 0)}")
    print(f"Chunks created  : {stats.get('num_chunks', 0)}")
    print(f"Index size      : {stats.get('index_size', 0)}")
    print("="*40)

if __name__ == "__main__":
    main()

import csv
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

import fitz  # PyMuPDF
import docx
from bs4 import BeautifulSoup

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    source_file: str
    page_number: Optional[int]
    chunk_index: int
    char_start: int
    char_end: int
    metadata: Dict[str, Any] = field(default_factory=dict)

class DocumentChunker:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def parse_file(self, filepath: Path) -> str:
        suffix = filepath.suffix.lower()
        if suffix == '.pdf':
            return self._parse_pdf(filepath)
        elif suffix == '.docx':
            return self._parse_docx(filepath)
        elif suffix in ('.html', '.htm'):
            return self._parse_html(filepath)
        elif suffix == '.csv':
            return self._parse_csv(filepath)
        elif suffix in ('.md', '.txt'):
            return self._parse_text(filepath)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _parse_pdf(self, path: Path) -> str:
        text = ""
        try:
            with fitz.open(path) as doc:
                for page in doc:
                    text += page.get_text() + "\n\n"
        except Exception as e:
            raise RuntimeError(f"Failed to parse PDF {path}: {e}")
        return text


    def _parse_pdf_pages(self, path: Path) -> List[tuple[int, str]]:
        """Preserve page provenance so PDF citations can point to a location."""
        try:
            with fitz.open(path) as doc:
                return [(page.number + 1, page.get_text()) for page in doc]
        except Exception as e:
            raise RuntimeError(f"Failed to parse PDF {path}: {e}")
    def _parse_docx(self, path: Path) -> str:
        text = ""
        try:
            doc = docx.Document(path)
            for para in doc.paragraphs:
                text += para.text + "\n\n"
        except Exception as e:
            raise RuntimeError(f"Failed to parse DOCX {path}: {e}")
        return text

    def _parse_html(self, path: Path) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                return soup.get_text(separator='\n\n')
        except Exception as e:
            raise RuntimeError(f"Failed to parse HTML {path}: {e}")

    def _parse_csv(self, path: Path) -> str:
        text = ""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    text += " | ".join(f"{k}: {v}" for k, v in row.items()) + "\n\n"
        except Exception as e:
            raise RuntimeError(f"Failed to parse CSV {path}: {e}")
        return text

    def _parse_text(self, path: Path) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise RuntimeError(f"Failed to parse Text file {path}: {e}")

    def chunk_text(self, text: str, source_file: str, page_number: Optional[int] = None) -> List[Chunk]:
        doc_id = hashlib.sha256(source_file.encode("utf-8")).hexdigest()
        separators = ['\n\n', '\n', '. ', ' ', '']
        
        def get_recursive_chunks(text: str) -> List[tuple[int, int, str]]:
            chunks = []
            char_idx = 0
            while char_idx < len(text):
                end_idx = min(char_idx + self.chunk_size, len(text))
                if end_idx < len(text):
                    cut_end = end_idx
                    for sep in separators[:-1]:
                        last_sep = text.rfind(sep, char_idx, end_idx)
                        if last_sep != -1 and last_sep > char_idx:
                            cut_end = last_sep + len(sep)
                            break
                    end_idx = cut_end
                
                chunk_str = text[char_idx:end_idx]
                chunks.append((char_idx, end_idx, chunk_str))
                char_idx += max(1, len(chunk_str) - self.chunk_overlap)
            return chunks

        raw_chunks = get_recursive_chunks(text)
        chunks = []
        
        for idx, (char_start, char_end, chunk_text) in enumerate(raw_chunks):
            chunk_id_seed = f"{doc_id}:{page_number}:{char_start}:{char_end}:{chunk_text}"
            chunk = Chunk(
                chunk_id=hashlib.sha256(chunk_id_seed.encode("utf-8")).hexdigest(),
                doc_id=doc_id,
                text=chunk_text,
                source_file=source_file,
                page_number=page_number,
                chunk_index=idx,
                char_start=char_start,
                char_end=char_end,
                metadata={}
            )
            chunks.append(chunk)
            
        return chunks

    def process_directory(self, docs_dir: Path) -> List[Chunk]:
        all_chunks = []
        supported_extensions = {'.pdf', '.docx', '.html', '.htm', '.csv', '.md', '.txt'}
        
        if not docs_dir.exists() or not docs_dir.is_dir():
            raise ValueError(f"Invalid directory: {docs_dir}")
            
        for filepath in docs_dir.rglob('*'):
            if filepath.is_file() and filepath.suffix.lower() in supported_extensions:
                try:
                    source_file = str(filepath.relative_to(docs_dir))
                    if filepath.suffix.lower() == '.pdf':
                        for page_number, text in self._parse_pdf_pages(filepath):
                            all_chunks.extend(self.chunk_text(text, source_file, page_number))
                    else:
                        text = self.parse_file(filepath)
                        all_chunks.extend(self.chunk_text(text, source_file))
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")
                    
        return all_chunks

"""Build SolidPilot's local, page-level PDF reference index.

The source PDFs remain outside the repository. Extracted page text is written beneath
`.solidpilot/`, which is gitignored. Requires pypdf only when rebuilding the index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / ".solidpilot" / "references.json"
DEFAULT_OUTPUT = ROOT / ".solidpilot" / "reference-index"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_text(value: str) -> str:
    value = value.translate(str.maketrans({
        "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
        "\ufb03": "ffi", "\ufb04": "ffl",
    }))
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s*\n\s*", "\n", value)
    return value.strip()


def build(manifest_path: Path, output_dir: Path) -> None:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit(
            "pypdf is required to rebuild the local reference index. "
            "Run this script with the Codex bundled Python or install pypdf locally."
        ) from exc

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = manifest.get("sources") or []
    if not sources:
        raise SystemExit(f"No sources found in {manifest_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = {"schema_version": 1, "sources": []}

    for source in sources:
        source_id = source["id"]
        pdf_path = Path(source["path"]).expanduser().resolve()
        if not pdf_path.is_file():
            raise SystemExit(f"Reference PDF not found: {pdf_path}")

        reader = PdfReader(str(pdf_path))
        digest = sha256(pdf_path)
        index_path = output_dir / f"{source_id}.jsonl"
        extracted_pages = 0

        with index_path.open("w", encoding="utf-8", newline="\n") as stream:
            for page_index, page in enumerate(reader.pages):
                text = clean_text(page.extract_text() or "")
                if not text:
                    continue
                extracted_pages += 1
                record = {
                    "source_id": source_id,
                    "title": source["title"],
                    "path": str(pdf_path),
                    "page": page_index + 1,
                    "text": text,
                }
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")

        catalog["sources"].append(
            {
                "id": source_id,
                "title": source["title"],
                "edition": source.get("edition"),
                "topics": source.get("topics", []),
                "path": str(pdf_path),
                "sha256": digest,
                "pages": len(reader.pages),
                "indexed_pages": extracted_pages,
                "index_file": index_path.name,
            }
        )
        print(f"Indexed {source_id}: {extracted_pages}/{len(reader.pages)} pages")

    (output_dir / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Catalog: {output_dir / 'catalog.json'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.manifest.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()

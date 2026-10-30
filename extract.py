"""Extract paragraphs and tables from a DOCX into a UTF-8 text file."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Path to the source .docx file")
    parser.add_argument("output", type=Path, help="Path to the output .txt file")
    args = parser.parse_args()

    try:
        from docx import Document
    except ImportError as exc:
        raise SystemExit("Install python-docx to use this utility: pip install python-docx") from exc

    document = Document(args.input)
    with args.output.open("w", encoding="utf-8", newline="\n") as output:
        for index, paragraph in enumerate(document.paragraphs):
            style = paragraph.style.name if paragraph.style else "None"
            output.write(f"[{index}][{style}] {paragraph.text}\n")

        for table_index, table in enumerate(document.tables):
            output.write(f"\n=== TABLE {table_index} ===\n")
            for row_index, row in enumerate(table.rows):
                output.write(f"  ROW {row_index}: {' | '.join(cell.text for cell in row.cells)}\n")


if __name__ == "__main__":
    main()

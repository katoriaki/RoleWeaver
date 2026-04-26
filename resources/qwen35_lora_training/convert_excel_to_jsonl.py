import argparse
import csv
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return max(index - 1, 0)


def _read_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values = []
    for item in root.findall("main:si", NS):
        parts = []
        for text in item.findall(".//main:t", NS):
            parts.append(text.text or "")
        values.append("".join(parts))
    return values


def _first_sheet_path(zf: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    first_sheet = workbook.find("main:sheets/main:sheet", NS)
    if first_sheet is None:
        raise ValueError("Workbook has no sheets.")
    rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall("rel:Relationship", NS):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib.get("Target", "")
            target = target.lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target
    raise ValueError("Could not resolve the first worksheet.")


def _cell_text(cell: ET.Element, shared_strings: List[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text_node = cell.find("main:is/main:t", NS)
        return (text_node.text or "") if text_node is not None else ""
    value_node = cell.find("main:v", NS)
    if value_node is None:
        return ""
    value = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return ""
    return value


def read_xlsx_rows(path: Path) -> List[List[str]]:
    rows = []
    with zipfile.ZipFile(path) as zf:
        shared_strings = _read_shared_strings(zf)
        sheet_path = _first_sheet_path(zf)
        sheet = ET.fromstring(zf.read(sheet_path))
        for row in sheet.findall(".//main:sheetData/main:row", NS):
            values = []
            for cell in row.findall("main:c", NS):
                ref = cell.attrib.get("r", "")
                column = _column_index(ref)
                while len(values) <= column:
                    values.append("")
                values[column] = _cell_text(cell, shared_strings).strip()
            rows.append(values)
    return rows


def read_csv_rows(path: Path) -> List[List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [[(cell or "").strip() for cell in row] for row in csv.reader(f)]


def header_index(headers: List[str], name: str) -> Optional[int]:
    normalized = [header.strip().lower() for header in headers]
    aliases = {
        "user": {"user", "用户", "提问", "input", "prompt"},
        "assistant": {"assistant", "回复", "回答", "response", "completion", "output"},
    }
    for index, header in enumerate(normalized):
        if header in aliases[name]:
            return index
    return None


def convert_rows(rows: List[List[str]]) -> List[dict]:
    if not rows:
        raise ValueError("Input table is empty.")
    user_index = header_index(rows[0], "user")
    assistant_index = header_index(rows[0], "assistant")
    if user_index is None or assistant_index is None:
        raise ValueError("First row must contain user and assistant columns.")

    records = []
    for row_number, row in enumerate(rows[1:], start=2):
        user = row[user_index].strip() if user_index < len(row) else ""
        assistant = row[assistant_index].strip() if assistant_index < len(row) else ""
        if not user and not assistant:
            continue
        if not user or not assistant:
            raise ValueError(f"Row {row_number} must have both user and assistant text.")
        records.append({
            "messages": [
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ]
        })
    if not records:
        raise ValueError("No training rows found after the header row.")
    return records


def convert_file(input_path: Path, output_path: Path) -> int:
    suffix = input_path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xltx"}:
        rows = read_xlsx_rows(input_path)
    elif suffix == ".csv":
        rows = read_csv_rows(input_path)
    else:
        raise ValueError("Input must be .xlsx, .xlsm, .xltx, or .csv.")

    records = convert_rows(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(records)


def main():
    parser = argparse.ArgumentParser(description="Convert a two-column Excel/CSV role SFT table to messages JSONL.")
    parser.add_argument("--input", required=True, help="Input .xlsx/.csv path. First row must be user, assistant.")
    parser.add_argument("--output", required=True, help="Output JSONL path.")
    args = parser.parse_args()

    count = convert_file(Path(args.input), Path(args.output))
    print(f"converted {count} rows to {args.output}")


if __name__ == "__main__":
    main()

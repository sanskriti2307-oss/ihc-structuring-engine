from __future__ import annotations

import argparse
import json
from pathlib import Path

from ihc_tool.ihc_engine import process_case


def build_case(input_id: str, raw_text: str, specimen: str) -> dict:
    return {
        "input_id": input_id,
        "input_type": "text",
        "raw_text": raw_text,
        "context": {
            "case_id": None,
            "specimen_id": specimen,
            "panel_hint": None,
        },
        "options": {
            "strict_mode": True,
            "allow_inference": False,
        },
        "metadata": {
            "source": "manual",
            "language": "en",
            "locale": "en-IN",
        },
    }


def run_batch(batch_path: Path, specimen: str, output_path: Path) -> list[dict]:
    text = batch_path.read_text().strip()
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    outputs = []
    marker_dict = Path(__file__).with_name("marker_dict.json")
    for idx, para in enumerate(paragraphs, start=1):
        case = build_case(f"case-{idx:02d}", para, specimen)
        outputs.append(process_case(case, marker_dict))

    output_path.write_text(json.dumps(outputs, indent=2))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="IHC Structuring Engine MVP-1")
    parser.add_argument("--batch", type=Path, required=True, help="Path to batch text file. Blank lines split cases.")
    parser.add_argument("--specimen", type=str, default="Specimen A")
    parser.add_argument("--output", type=Path, default=Path("ihc_outputs.json"))
    args = parser.parse_args()

    run_batch(args.batch, args.specimen, args.output)


if __name__ == "__main__":
    main()

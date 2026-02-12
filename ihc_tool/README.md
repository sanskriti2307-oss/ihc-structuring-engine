# IHC Structuring Engine (MVP-1)

Deterministic, rules-based parser for free-text IHC transcripts.

## Run

```bash
python -m ihc_tool.main --batch corner_cases.txt --specimen "Specimen A"
```

This writes `ihc_outputs.json` in the current directory.

## Test

```bash
pytest -q
```

## Design highlights
- Pure Python rules (no LLM calls).
- Conservative outputs (`needs_review`/`failed` when uncertain or incomplete).
- Handles Indian dictation aliases (e.g., `TTF one`, `P forty`, `Ki sixty seven`).
- Detects contradictions, missing required fields, invalid patterns, unknown markers, diagnostic-language leakage.

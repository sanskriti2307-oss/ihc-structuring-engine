# Schemas

## Input case schema
`main.py` builds and sends one case at a time to the engine with:
- `input_id: string`
- `input_type: text | asr`
- `raw_text: string`
- `context.case_id: string | null`
- `context.specimen_id: string | null`
- `context.panel_hint: string | null`
- `options.strict_mode: boolean`
- `options.allow_inference: boolean`
- `metadata.source: manual | asr`
- `metadata.language: string`
- `metadata.locale: string`

## Output schema
`ihc_engine.process_case()` returns:
- `output_id: string`
- `input_id: string`
- `status: ok | needs_review | failed`
- `ihc.panel_name, case_id, specimen_id`
- `ihc.markers[]` entries with marker/result/pattern/intensity/percent/extent/controls/comment/confidence/evidence
- `rendered.narrative`
- `rendered.table[]`
- `validation.errors[]` and `validation.warnings[]`
- `provenance.source_type`, `extraction_model=rules-v1`, `version=ihc-mvp-1`

## Notes
- Blank-line-separated paragraphs are independent cases.
- `strict_mode` is respected by conservative validation: missing mandatory elements become errors.

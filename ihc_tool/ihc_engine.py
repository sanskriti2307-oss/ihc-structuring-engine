from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DIAGNOSTIC_RE = re.compile(r"\b(supports?|consistent with|suggestive of|favor|favours?|primary|metastasis|metastatic)\b", re.I)
RESULT_POS_RE = re.compile(r"\b(positive|positivity)\b", re.I)
RESULT_NEG_RE = re.compile(r"\bnegative\b", re.I)
RESULT_NOT_DONE_RE = re.compile(r"\b(not\s+done|awaited|pending)\b", re.I)
PATTERN_RE = re.compile(r"\b(nuclear|cytoplasmic|membranous)\b", re.I)
INTENSITY_RE = re.compile(r"\b(weak|moderate|strong)\b", re.I)
EXTENT_RE = re.compile(r"\b(focal|diffuse)\b", re.I)
UNKNOWN_MARKER_RE = re.compile(r"\b([A-Za-z]{2,}\d*)\s+(?:positive|negative)\b")

WORDS = {
    "zero": 0,
    "ten": 10,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
}


@dataclass
class MarkerDef:
    marker_canonical: str
    display_name: str
    aliases: list[str]
    hard_pattern_enforce: bool
    allowed_patterns: list[str]
    requirements: dict[str, bool]


@dataclass
class MarkerState:
    marker_name: str
    marker_canonical: str
    result: str | None = None
    pattern: str | None = None
    intensity: str | None = None
    percent_positive: float | None = None
    extent: str | None = None
    controls: str | None = "not mentioned"
    comment: str | None = None
    confidence: str = "explicit"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    percent_approximate: bool = False


def _load_dict(path: str | Path) -> tuple[list[MarkerDef], dict[str, MarkerDef]]:
    data = json.loads(Path(path).read_text())
    defs = [MarkerDef(**m) for m in data["markers"]]
    amap: dict[str, MarkerDef] = {}
    for m in defs:
        for alias in m.aliases:
            amap[re.sub(r"\s+", " ", alias.strip().lower())] = m
    return defs, amap


def _to_num_word(token: str) -> int | None:
    token = token.lower().strip()
    if token in WORDS:
        return WORDS[token]
    return None


def _parse_percent(text: str) -> tuple[float | None, bool]:
    t = text.lower()
    range_match = re.search(r"\b(\w+|\d+)\s+to\s+(\w+|\d+)\s+percent\b", t)
    if range_match:
        return None, True
    m = re.search(r"\b(\d{1,3})\s*%\b", t) or re.search(r"\b(\d{1,3})\s+percent\b", t)
    if m:
        return float(m.group(1)), False
    m2 = re.search(r"\b(\w+)\s+percent\b", t)
    if m2:
        val = _to_num_word(m2.group(1))
        if val is not None:
            return float(val), False
    return None, False


def _find_markers(text: str, alias_map: dict[str, MarkerDef]) -> list[tuple[MarkerDef, tuple[int, int], str]]:
    found: list[tuple[MarkerDef, tuple[int, int], str]] = []
    lower = text.lower()
    for alias, md in alias_map.items():
        for m in re.finditer(rf"\b{re.escape(alias)}\b", lower):
            found.append((md, m.span(), text[m.start():m.end()]))
    found.sort(key=lambda x: (x[1][0], -(x[1][1] - x[1][0])))
    dedup: list[tuple[MarkerDef, tuple[int, int], str]] = []
    used: list[tuple[int, int]] = []
    for item in found:
        s, e = item[1]
        if any(s >= us and e <= ue for us, ue in used):
            continue
        used.append((s, e))
        dedup.append(item)
    return dedup




def split_clause_by_markers(clause: str, marker_spans: list[tuple[MarkerDef, tuple[int, int], str]]) -> list[tuple[str, str, str]]:
    """Split a clause into marker-scoped segments from each marker start to the next marker start."""
    if not marker_spans:
        return []

    ordered = sorted(marker_spans, key=lambda x: x[1][0])
    segments: list[tuple[str, str, str]] = []

    for idx, (md, span, _alias_text) in enumerate(ordered):
        start = span[0]
        end = ordered[idx + 1][1][0] if idx + 1 < len(ordered) else len(clause)
        segment_text = clause[start:end].strip(' ,;')
        segments.append((md.marker_canonical, md.display_name, segment_text))

    return segments

def _extract_clause_data(clause: str) -> dict[str, Any]:
    lower = clause.lower()
    result = None
    if RESULT_NOT_DONE_RE.search(lower):
        result = "Not Done"
    elif RESULT_POS_RE.search(lower):
        result = "Positive"
    elif RESULT_NEG_RE.search(lower):
        result = "Negative"

    pattern = None
    pm = PATTERN_RE.search(lower)
    if pm:
        pattern = pm.group(1).lower()

    intensity = None
    im = INTENSITY_RE.search(lower)
    if im:
        intensity = im.group(1).lower()

    extent = None
    em = EXTENT_RE.search(lower)
    if em:
        extent = em.group(1).lower()

    percent, approximate = _parse_percent(lower)

    controls = "not mentioned"
    if re.search(r"\b(control|controls|internal control)\b", lower):
        if "inadequate" in lower:
            controls = "inadequate"
        elif re.search(r"\b(adequate|fine)\b", lower):
            controls = "adequate"

    confidence = "explicit"
    if re.search(r"\b(maybe|kind of|around)\b", lower):
        confidence = "uncertain"

    return {
        "result": result,
        "pattern": pattern,
        "intensity": intensity,
        "extent": extent,
        "percent_positive": percent,
        "percent_approximate": approximate,
        "controls": controls,
        "confidence": confidence,
    }


def _split_clauses(text: str) -> list[str]:
    text = text.replace("\n", ". ")
    clauses = [c.strip() for c in re.split(r"[.;]+", text) if c.strip()]
    return clauses


def process_case(case: dict[str, Any], marker_dict_path: str | Path) -> dict[str, Any]:
    _defs, alias_map = _load_dict(marker_dict_path)
    raw = case["raw_text"].strip()
    clauses = _split_clauses(raw)

    markers: dict[str, MarkerState] = {}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if DIAGNOSTIC_RE.search(raw):
        warnings.append({"code": "DIAGNOSTIC_LANGUAGE_DETECTED", "message": "Diagnostic language found in input.", "severity": "warning", "marker_canonical": None, "field": None})

    for clause in clauses:
        found = _find_markers(clause, alias_map)
        marker_segments = split_clause_by_markers(clause, found)

        negative_for_clause = bool(re.search(r"\bnegative\s+for\b", clause, re.I))
        clause_level_data = _extract_clause_data(clause)

        for marker_canonical, marker_name, segment_text in marker_segments:
            clause_data = _extract_clause_data(segment_text)
            if clause_data["result"] is None and clause_level_data["result"] in {"Positive", "Negative", "Not Done"}:
                clause_data["result"] = clause_level_data["result"]
            if negative_for_clause and clause_data["result"] is None:
                clause_data["result"] = "Negative"

            ms = markers.get(marker_canonical)
            if not ms:
                ms = MarkerState(marker_name=marker_name, marker_canonical=marker_canonical)
                markers[marker_canonical] = ms

            prev_result = ms.result
            inferred_result = clause_data["result"]
            has_supporting_attributes = any(
                [
                    clause_data["intensity"] is not None,
                    clause_data["pattern"] is not None,
                    clause_data["percent_positive"] is not None,
                    clause_data["percent_approximate"],
                    clause_data["extent"] is not None,
                ]
            )
            if inferred_result is None and has_supporting_attributes:
                inferred_result = "Positive"
                ms.confidence = "inferred"
                warnings.append({"code": "RESULT_INFERRED", "message": f"Result inferred from attributes for {marker_canonical}.", "severity": "warning", "marker_canonical": marker_canonical, "field": "result"})

            if inferred_result is not None:
                if prev_result and prev_result != inferred_result:
                    errors.append({"code": "CONTRADICTORY_RESULT", "message": f"Conflicting results for {marker_canonical}.", "severity": "error", "marker_canonical": marker_canonical, "field": "result"})
                ms.result = inferred_result

            for fld in ["pattern", "intensity", "extent", "percent_positive"]:
                val = clause_data[fld]
                if val is not None:
                    setattr(ms, fld, val)

            if clause_data["controls"] != "not mentioned":
                ms.controls = clause_data["controls"]

            if clause_data["confidence"] != "explicit":
                ms.confidence = "uncertain"
                warnings.append({"code": "LOW_CONFIDENCE", "message": f"Uncertain wording for {marker_canonical}.", "severity": "warning", "marker_canonical": marker_canonical, "field": None})

            if clause_data["percent_approximate"]:
                ms.percent_approximate = True
                warnings.append({"code": "PERCENT_APPROXIMATE", "message": f"Approximate/range percent for {marker_canonical}.", "severity": "warning", "marker_canonical": marker_canonical, "field": "percent_positive"})

            ms.evidence.append({"text_span": segment_text, "start_char": None, "end_char": None})

        # unknown markers (only if shape like "CD positive" and not found known marker)
        if not found:
            for um in UNKNOWN_MARKER_RE.finditer(clause):
                token = um.group(1)
                if len(token) <= 2:
                    continue
                errors.append({"code": "UNKNOWN_MARKER", "message": f"Unknown marker: {token}", "severity": "error", "marker_canonical": None, "field": "marker_name"})

    if not markers:
        errors.append({"code": "NO_MARKERS_FOUND", "message": "No known markers found.", "severity": "error", "marker_canonical": None, "field": None})

    defs_by_can = {d.marker_canonical: d for d in _defs}
    for can, ms in markers.items():
        md = defs_by_can[can]
        req = md.requirements

        if ms.result is None:
            errors.append({"code": "RESULT_MISSING", "message": f"Missing result for {can}.", "severity": "error", "marker_canonical": can, "field": "result"})

        if ms.result == "Negative" and ms.percent_positive is not None and ms.percent_positive > 0:
            errors.append({"code": "CONTRADICTORY_RESULT_PERCENT", "message": f"Negative result with non-zero percent for {can}.", "severity": "error", "marker_canonical": can, "field": "percent_positive"})

        if ms.pattern is not None and ms.pattern not in md.allowed_patterns:
            if md.hard_pattern_enforce:
                errors.append({"code": "INVALID_PATTERN", "message": f"Invalid pattern for {can}: {ms.pattern}", "severity": "error", "marker_canonical": can, "field": "pattern"})
            else:
                warnings.append({"code": "UNUSUAL_PATTERN", "message": f"Unusual pattern for {can}: {ms.pattern}", "severity": "warning", "marker_canonical": can, "field": "pattern"})

        if req.get("percent_required") and ms.result != "Not Done" and ms.percent_positive is None:
            if ms.percent_approximate:
                warnings.append({"code": "PERCENT_REQUIRED_MISSING", "message": f"Exact percent required for {can}; approximate provided.", "severity": "warning", "marker_canonical": can, "field": "percent_positive"})
            else:
                errors.append({"code": "PERCENT_REQUIRED_MISSING", "message": f"Percent required for {can}.", "severity": "error", "marker_canonical": can, "field": "percent_positive"})

        if req.get("intensity_required") and ms.result != "Not Done" and ms.intensity is None:
            errors.append({"code": "INTENSITY_REQUIRED_MISSING", "message": f"Intensity required for {can}.", "severity": "error", "marker_canonical": can, "field": "intensity"})

        if ms.percent_positive is not None and not (0 <= ms.percent_positive <= 100):
            errors.append({"code": "PERCENT_OUT_OF_RANGE", "message": f"Percent out of range for {can}.", "severity": "error", "marker_canonical": can, "field": "percent_positive"})

    table = []
    lines = []
    specimen = case.get("context", {}).get("specimen_id") or "Specimen A"
    for ms in markers.values():
        table.append({
            "marker": ms.marker_name,
            "result": ms.result or "",
            "pattern": ms.pattern,
            "intensity": ms.intensity,
            "percent_positive": ms.percent_positive,
            "extent": ms.extent,
            "comment": ms.comment,
        })
        if ms.result:
            pieces = [ms.result]
            if ms.pattern:
                pieces.append(ms.pattern)
            if ms.intensity:
                pieces.append(ms.intensity)
            if ms.percent_positive is not None:
                pieces.append(f"in {int(ms.percent_positive)}% of cells")
            lines.append(f"{ms.marker_name}: {', '.join(pieces)}.")

    narrative = None
    if markers:
        narrative = "Immunohistochemistry (" + specimen + "):\n" + "\n".join(lines)

    status = "ok"
    if errors:
        status = "failed"
    elif warnings:
        status = "needs_review"

    return {
        "output_id": str(uuid.uuid4()),
        "input_id": case["input_id"],
        "status": status,
        "ihc": {
            "panel_name": case.get("context", {}).get("panel_hint"),
            "case_id": case.get("context", {}).get("case_id"),
            "specimen_id": case.get("context", {}).get("specimen_id"),
            "markers": [{k:v for k,v in ms.__dict__.items() if k!="percent_approximate"} for ms in markers.values()],
        },
        "rendered": {"narrative": narrative, "table": table},
        "validation": {"errors": errors, "warnings": warnings},
        "provenance": {"source_type": case["input_type"], "extraction_model": "rules-v1", "version": "ihc-mvp-1"},
    }

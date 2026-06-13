#!/usr/bin/env python3
"""Brief intake gate for techne/intake.

Python 3 stdlib only. POSIX developer environments only.

The gate computes bookkeeping over a user-authored written brief and a
skill-fixed engineering implementation rubric. It verifies offsets/quotes
against the brief, value grounding against verbatim spans, question binding, and
intent-level plan DAG integrity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTEXT_SCHEMA = "techne.intake.context/1"
INTAKE_SCHEMA = "techne.intake/1"
REPORT_SCHEMA = "techne.intake.report/1"
PLAN_SCHEMA = "techne.intake.plan/1"
INTAKE_REPORT_SCHEMA = "techne.intake.intakeReport/1"
RUBRIC_ID = "engineering-implementation-brief-v1"

RUBRIC: list[dict[str, Any]] = [
    {
        "id": "goal-and-why",
        "label": "Goal and why",
        "definition": "The intended end state and the reason it matters.",
        "indicatorTerms": ["goal", "why", "because", "so that", "problem", "outcome"],
    },
    {
        "id": "users-stakeholders",
        "label": "Users and stakeholders",
        "definition": "The people, teams, systems, or roles affected by the work.",
        "indicatorTerms": ["user", "users", "stakeholder", "customer", "team", "admin", "operator"],
    },
    {
        "id": "measurable-success-threshold",
        "label": "Measurable success threshold",
        "definition": "A measurable condition that says when the work succeeds.",
        "indicatorTerms": ["success", "metric", "threshold", "measure", "latency", "deadline", "p95", "sla"],
        "shape": "metric-plus-threshold",
    },
    {
        "id": "scope-in",
        "label": "Scope in",
        "definition": "The concrete behavior or deliverable included in this work.",
        "indicatorTerms": ["scope", "include", "build", "implement", "deliver", "in scope", "must"],
    },
    {
        "id": "non-goals",
        "label": "Non-goals",
        "definition": "Explicitly excluded behavior, audiences, platforms, or deliverables.",
        "indicatorTerms": ["non-goal", "non goal", "out of scope", "not included", "exclude", "defer"],
    },
    {
        "id": "inputs",
        "label": "Inputs",
        "definition": "Inputs the implementation consumes, such as user fields, files, events, or parameters.",
        "indicatorTerms": ["input", "field", "parameter", "payload", "event", "file", "form"],
    },
    {
        "id": "data-sources",
        "label": "Data sources",
        "definition": "Authoritative sources of data the implementation reads or writes.",
        "indicatorTerms": ["data", "source", "database", "api", "warehouse", "table", "endpoint", "jira"],
    },
    {
        "id": "external-dependencies",
        "label": "External dependencies",
        "definition": "External systems, APIs, services, approvals, credentials, or teams the work depends on.",
        "indicatorTerms": ["dependency", "depends", "api", "service", "vendor", "approval", "credential", "oauth"],
    },
    {
        "id": "constraints",
        "label": "Constraints",
        "definition": "Limits on implementation such as compatibility, security, privacy, platform, time, or style.",
        "indicatorTerms": ["constraint", "limit", "must not", "security", "privacy", "platform", "compatible"],
    },
    {
        "id": "acceptance-method",
        "label": "Acceptance method",
        "definition": "How the result will be verified, checked, reviewed, tested, or signed off.",
        "indicatorTerms": ["acceptance", "verify", "verification", "test", "check", "review", "sign-off"],
        "shape": "verification-action",
    },
]

RUBRIC_IDS = [item["id"] for item in RUBRIC]
RUBRIC_BY_ID = {item["id"]: item for item in RUBRIC}

STOPLIST = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "done",
    "for",
    "from",
    "had",
    "has",
    "have",
    "having",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "might",
    "must",
    "of",
    "on",
    "or",
    "our",
    "shall",
    "should",
    "so",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "this",
    "those",
    "through",
    "to",
    "use",
    "used",
    "using",
    "via",
    "was",
    "we",
    "were",
    "will",
    "with",
    "would",
}

RUBRIC_LABEL_TOKENS = {
    "acceptance",
    "constraint",
    "constraints",
    "data",
    "deadline",
    "deliverable",
    "dependency",
    "dependencies",
    "external",
    "goal",
    "goals",
    "input",
    "inputs",
    "measurable",
    "method",
    "non",
    "outcome",
    "scope",
    "source",
    "sources",
    "stakeholder",
    "stakeholders",
    "success",
    "threshold",
    "user",
    "users",
    "verification",
    "why",
}

ALLOWED_DISPOSITIONS = {"present", "present-weak", "gap"}
VERIFICATION_ACTION_RE = re.compile(
    r"\b(?:test(?:s|ed|ing)?|check(?:s|ed|ing)?|review(?:s|ed|ing)?|"
    r"verify|verifies|verified|verification|validate|validates|validated|validation|"
    r"sign[- ]?off|qa)\b",
    re.IGNORECASE,
)
COMPARATOR_RE = re.compile(
    r"(?:<=|>=|<|>|≤|≥|\bunder\b|\bwithin\b|\bby\b|\bbefore\b|\bafter\b|"
    r"\bat least\b|\bat most\b|\bno more than\b|\bno less than\b|\bbelow\b|\babove\b)",
    re.IGNORECASE,
)
NUMBER_UNIT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ms|msec|s|sec|secs|second|seconds|min|mins|minute|minutes|"
    r"h|hr|hrs|hour|hours|day|days|%|percent|kb|mb|gb|tb|requests?|users?|errors?|"
    r"items?|rows?|records?|am|pm)\b",
    re.IGNORECASE,
)
WORD_NUMBER_UNIT_RE = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"(?:second|seconds|minute|minutes|hour|hours|day|days|user|users|item|items)\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
    r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?|mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|"
    r"thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b",
    re.IGNORECASE,
)
THRESHOLD_NOISE = {
    "am",
    "above",
    "after",
    "at",
    "before",
    "below",
    "by",
    "day",
    "days",
    "deadline",
    "hour",
    "hours",
    "less",
    "min",
    "mins",
    "minute",
    "minutes",
    "more",
    "ms",
    "msec",
    "no",
    "one",
    "pm",
    "sec",
    "second",
    "seconds",
    "seven",
    "six",
    "than",
    "three",
    "two",
    "under",
    "within",
    "utc",
    "four",
    "five",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_posix() -> None:
    if os.name != "posix":
        raise SystemExit("intake_gate.py v1 supports POSIX developer environments only (macOS/Linux).")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip(".-_")
    return slug or "intake"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


def json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing required artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def fail(kind: str, message: str, extra: dict[str, Any] | None = None) -> None:
    payload = {"ok": False, "failureKind": kind, "message": message}
    if extra:
        payload.update(extra)
    print_json(payload)
    raise SystemExit(1)


def resolve_project(value: Path) -> Path:
    project = value.resolve()
    if not project.is_dir():
        raise SystemExit(f"Project directory does not exist: {project}")
    return project


def ensure_gitignore(project: Path) -> None:
    gitignore = project / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if ".techne/" not in [line.strip() for line in existing]:
        prefix = "" if not existing or existing[-1] == "" else "\n"
        with gitignore.open("a", encoding="utf-8") as handle:
            handle.write(f"{prefix}.techne/\n")


def plan_dir(project: Path, plan: str) -> Path:
    return project / ".techne" / "plan" / slugify(plan)


def normalize_for_tokens(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    chars: list[str] = []
    for char in normalized:
        category = unicodedata.category(char)
        if char.isalnum():
            chars.append(char)
        elif char.isspace() or category.startswith("P") or category.startswith("S"):
            chars.append(" ")
        else:
            chars.append(" ")
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def raw_tokens(value: str) -> list[str]:
    normalized = normalize_for_tokens(value)
    return normalized.split() if normalized else []


def content_tokens(value: str) -> list[str]:
    return [
        token
        for token in raw_tokens(value)
        if token not in STOPLIST and token not in RUBRIC_LABEL_TOKENS
    ]


def citation_quote(citation: Any) -> str | None:
    if isinstance(citation, dict):
        value = citation.get("quote", citation.get("quoted", citation.get("text")))
        return value if isinstance(value, str) else None
    return None


def citation_offset(citation: Any) -> int | None:
    if isinstance(citation, dict) and isinstance(citation.get("offset"), int):
        return citation["offset"]
    return None


def verify_offset_quote(brief: str, citation: Any) -> tuple[bool, str]:
    """Verify a vet-style offset + quoted-substring citation against the brief."""
    if not isinstance(citation, dict):
        return False, "citation must be an object with offset and quote"
    offset = citation_offset(citation)
    quote = citation_quote(citation)
    if offset is None:
        return False, "citation offset must be an integer"
    if quote is None or quote == "":
        return False, "citation quote must be a non-empty string"
    if offset < 0 or offset + len(quote) > len(brief):
        return False, "citation offset is out of range"
    if brief[offset : offset + len(quote)] != quote:
        return False, "citation quote does not match brief at offset"
    return True, "verified"


def resolve_span(brief: str, span: Any) -> tuple[bool, str, str]:
    if isinstance(span, str):
        if span and span in brief:
            return True, span, "verified"
        return False, span if isinstance(span, str) else "", "valueSpan string is not a contiguous brief substring"
    ok, message = verify_offset_quote(brief, span)
    quote = citation_quote(span) or ""
    return ok, quote, message


def add_issue(target: list[dict[str, Any]], kind: str, path: str, message: str, extra: dict[str, Any] | None = None) -> None:
    issue = {"kind": kind, "path": path, "message": message}
    if extra:
        issue.update(extra)
    target.append(issue)


def read_brief_from_args(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    has_file = args.brief_file is not None
    has_text = args.brief_text is not None
    if has_file == has_text:
        raise SystemExit("init requires exactly one of --brief-file or --brief-text")
    if has_text:
        return args.brief_text, {"kind": "inline"}
    if args.brief_file == "-":
        text = sys.stdin.read()
        return text, {"kind": "stdin"}
    path = Path(args.brief_file).resolve()
    text = path.read_text(encoding="utf-8")
    return text, {"kind": "file", "path": str(path)}


def rubric_manifest() -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "definition": item["definition"],
            "shape": item.get("shape"),
            "indicatorTerms": item["indicatorTerms"],
        }
        for item in RUBRIC
    ]


def normalize_elements(raw: Any) -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(key): value for key, value in raw.items() if isinstance(value, dict)}
    if isinstance(raw, list):
        elements: dict[str, dict[str, Any]] = {}
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                copied = dict(item)
                element_id = copied.pop("id")
                elements[element_id] = copied
        return elements
    return {}


def intake_elements(intake: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return normalize_elements(intake.get("elements", intake.get("rubric")))


def question_id(question: dict[str, Any], index: int) -> str:
    value = question.get("id")
    return value if isinstance(value, str) and value else f"q{index + 1}"


def normalize_ref(ref: Any) -> str | None:
    if not isinstance(ref, str) or not ref.strip():
        return None
    return ref.strip()


def ref_targets_element(ref: str, element_id: str) -> bool:
    return ref == element_id or ref == f"element:{element_id}"


def ref_target_id(ref: str) -> str:
    return ref.split(":", 1)[1] if ":" in ref else ref


def question_text(question: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("text", "question", "prompt"):
        value = question.get(key)
        if isinstance(value, str):
            parts.append(value)
    options = question.get("options")
    if isinstance(options, list):
        for option in options:
            if isinstance(option, dict):
                for key in ("label", "text", "answer"):
                    value = option.get(key)
                    if isinstance(value, str):
                        parts.append(value)
            elif isinstance(option, str):
                parts.append(option)
    return " ".join(parts)


def question_has_plan_delta(question: dict[str, Any]) -> bool:
    options = question.get("options")
    if isinstance(options, list) and options:
        for option in options:
            if not isinstance(option, dict) or not option.get("planDelta"):
                return False
        return True
    return bool(question.get("planDelta"))


def dependent_questions(element_id: str, element: dict[str, Any], questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    direct_ids: set[str] = set()
    raw_ids = element.get("questionIds", element.get("questions", []))
    if isinstance(raw_ids, str):
        direct_ids.add(raw_ids)
    elif isinstance(raw_ids, list):
        direct_ids.update(value for value in raw_ids if isinstance(value, str))
    matched: list[dict[str, Any]] = []
    for index, question in enumerate(questions):
        qid = question_id(question, index)
        resolves = question.get("resolves", [])
        if isinstance(resolves, str):
            resolves = [resolves]
        resolves_list = [normalize_ref(item) for item in resolves] if isinstance(resolves, list) else []
        if qid in direct_ids or any(ref and ref_targets_element(ref, element_id) for ref in resolves_list):
            matched.append(question)
    return matched


def has_model_default(element: dict[str, Any]) -> bool:
    value = element.get("modelDefault", element.get("flaggedDefault"))
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        text = value.get("text", value.get("value", value.get("reason")))
        return isinstance(text, str) and bool(text.strip())
    return True


def value_items_for(element: dict[str, Any]) -> list[dict[str, Any]]:
    items = element.get("valueItems")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def validate_value_items(
    brief: str,
    element_id: str,
    element: dict[str, Any],
    failures: list[dict[str, Any]],
    element_report: dict[str, Any],
) -> None:
    items = value_items_for(element)
    if not items:
        add_issue(
            failures,
            "present_without_value",
            f"/elements/{element_id}/valueItems",
            "present disposition requires non-empty valueItems",
        )
        return
    normalized_items: list[dict[str, Any]] = []
    for item_index, item in enumerate(items):
        text = item.get("text")
        spans = item.get("valueSpans")
        item_path = f"/elements/{element_id}/valueItems/{item_index}"
        if not isinstance(text, str) or not text.strip():
            add_issue(failures, "present_without_value", f"{item_path}/text", "value item text must be non-empty")
            continue
        if not isinstance(spans, list) or not spans:
            add_issue(
                failures,
                "value_item_not_contiguously_grounded",
                f"{item_path}/valueSpans",
                "value item requires at least one contiguous valueSpan",
            )
            add_issue(
                failures,
                "value_not_grounded_in_spans",
                item_path,
                "value item has no verified span to ground its content tokens",
            )
            continue
        span_reports: list[dict[str, Any]] = []
        span_token_sets: list[set[str]] = []
        for span_index, span in enumerate(spans):
            ok, quote, message = resolve_span(brief, span)
            span_report = {"index": span_index, "quote": quote, "verified": ok}
            if isinstance(span, dict) and isinstance(span.get("offset"), int):
                span_report["offset"] = span["offset"]
            span_reports.append(span_report)
            if not ok:
                add_issue(
                    failures,
                    "value_item_not_contiguously_grounded",
                    f"{item_path}/valueSpans/{span_index}",
                    message,
                )
                continue
            span_token_sets.append(set(content_tokens(quote)))
        tokens = content_tokens(text)
        if not tokens:
            add_issue(
                failures,
                "value_not_grounded_in_spans",
                f"{item_path}/text",
                "value item text has no content tokens after STOPLIST/RUBRIC-LABEL removal",
            )
        elif not any(set(tokens).issubset(token_set) for token_set in span_token_sets):
            add_issue(
                failures,
                "value_not_grounded_in_spans",
                item_path,
                "value item content tokens are not all present in one of its own valueSpans",
                {"contentTokens": tokens},
            )
        normalized_items.append({"text": text, "contentTokens": tokens, "valueSpans": span_reports})
    element_report["valueItems"] = normalized_items


def citation_list_for_finding(finding: dict[str, Any]) -> list[Any]:
    if "citation" in finding:
        return [finding["citation"]]
    value = finding.get("citations")
    return value if isinstance(value, list) else []


def finding_id(finding: dict[str, Any], index: int) -> str:
    value = finding.get("id")
    if isinstance(value, str) and value:
        return value
    kind = finding.get("kind", finding.get("type", "finding"))
    return f"{kind}-{index + 1}"


def finding_kind(finding: dict[str, Any]) -> str:
    value = finding.get("kind", finding.get("type"))
    return value if isinstance(value, str) else ""


def text_has_threshold(value: str) -> bool:
    return bool(
        COMPARATOR_RE.search(value)
        or NUMBER_UNIT_RE.search(value)
        or WORD_NUMBER_UNIT_RE.search(value)
        or DATE_RE.search(value)
    )


def text_has_metric_or_condition(value: str) -> bool:
    tokens = [
        token
        for token in content_tokens(value)
        if token not in THRESHOLD_NOISE and not re.fullmatch(r"p\d+", token) and not token.isdigit()
        and not any(char.isdigit() for char in token)
    ]
    return bool(tokens)


def shape_failure(element_id: str, items: list[dict[str, Any]]) -> str | None:
    text = " ".join(item.get("text", "") for item in items if isinstance(item.get("text"), str))
    if element_id == "measurable-success-threshold":
        if not text_has_metric_or_condition(text) or not text_has_threshold(text):
            return "requires both a metric/condition and a threshold, comparator, or deadline"
    if element_id == "acceptance-method":
        if not VERIFICATION_ACTION_RE.search(text):
            return "requires a verification action such as test, check, review, sign-off, or verify"
    return None


def question_bound_to_element(question: dict[str, Any], element_id: str, element: dict[str, Any], effective_disposition: str) -> bool:
    q_tokens = set(raw_tokens(question_text(question)))
    if not q_tokens:
        return False
    if effective_disposition == "gap":
        label_tokens = set(raw_tokens(element_id.replace("-", " ")))
        label = RUBRIC_BY_ID.get(element_id, {}).get("label", "")
        label_tokens.update(raw_tokens(label))
        for term in RUBRIC_BY_ID.get(element_id, {}).get("indicatorTerms", []):
            label_tokens.update(raw_tokens(term))
        label_tokens.update(token.rstrip("s") for token in list(label_tokens) if token.endswith("s"))
        q_tokens.update(token.rstrip("s") for token in list(q_tokens) if token.endswith("s"))
        return bool(q_tokens & label_tokens)
    evidence_tokens: set[str] = set()
    citation = element.get("citation")
    quote = citation_quote(citation)
    if quote:
        evidence_tokens.update(token for token in content_tokens(quote) if len(token) >= 3)
    for item in value_items_for(element):
        text = item.get("text")
        if isinstance(text, str):
            evidence_tokens.update(token for token in content_tokens(text) if len(token) >= 3)
    if not evidence_tokens:
        evidence_tokens.update(raw_tokens(element_id.replace("-", " ")))
    return bool(q_tokens & evidence_tokens)


def indicator_terms_present(brief: str, element_id: str) -> list[str]:
    normalized_brief = normalize_for_tokens(brief)
    brief_tokens = set(normalized_brief.split())
    hits: list[str] = []
    for term in RUBRIC_BY_ID[element_id]["indicatorTerms"]:
        norm_term = normalize_for_tokens(term)
        if not norm_term:
            continue
        term_tokens = norm_term.split()
        if len(term_tokens) == 1:
            if term_tokens[0] in brief_tokens:
                hits.append(term)
        elif f" {norm_term} " in f" {normalized_brief} ":
            hits.append(term)
    return hits


def validate_steps(
    intake: dict[str, Any],
    known_assumptions: set[str],
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_steps = intake.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps:
        add_issue(failures, "orphan_step", "/steps", "steps must contain at least one intent-level step")
        return {"steps": [], "terminalStepIds": [], "rootStepIds": []}
    steps = [step for step in raw_steps if isinstance(step, dict)]
    ids: list[str] = []
    step_by_id: dict[str, dict[str, Any]] = {}
    for index, step in enumerate(steps):
        step_id = step.get("id")
        path = f"/steps/{index}"
        if not isinstance(step_id, str) or not step_id:
            add_issue(failures, "orphan_step", f"{path}/id", "step id must be non-empty")
            continue
        if step_id in step_by_id:
            add_issue(failures, "orphan_step", f"{path}/id", f"duplicate step id: {step_id}")
            continue
        ids.append(step_id)
        step_by_id[step_id] = step
    id_set = set(ids)
    terminal_ids: list[str] = []
    roots: list[str] = []
    children: dict[str, set[str]] = {step_id: set() for step_id in ids}
    for index, step in enumerate(steps):
        step_id = step.get("id")
        if not isinstance(step_id, str) or step_id not in id_set:
            continue
        path = f"/steps/{index}"
        depends_steps = step.get("dependsOnSteps", [])
        if depends_steps is None:
            depends_steps = []
        if not isinstance(depends_steps, list):
            add_issue(failures, "step_dangling_ref", f"{path}/dependsOnSteps", "dependsOnSteps must be a list")
            depends_steps = []
        if not depends_steps:
            roots.append(step_id)
        for ref in depends_steps:
            if not isinstance(ref, str) or ref not in id_set:
                add_issue(failures, "step_dangling_ref", f"{path}/dependsOnSteps", f"unknown step ref: {ref!r}")
            else:
                children.setdefault(ref, set()).add(step_id)
        depends_assumptions = step.get("dependsOnAssumptions", [])
        if depends_assumptions is None:
            depends_assumptions = []
        if not isinstance(depends_assumptions, list):
            add_issue(
                failures,
                "step_dangling_ref",
                f"{path}/dependsOnAssumptions",
                "dependsOnAssumptions must be a list",
            )
            depends_assumptions = []
        for ref in depends_assumptions:
            if not isinstance(ref, str) or ref not in known_assumptions:
                add_issue(
                    failures,
                    "step_dangling_ref",
                    f"{path}/dependsOnAssumptions",
                    f"unknown assumption ref: {ref!r}",
                )
        if step.get("terminal") is True:
            terminal_ids.append(step_id)
        if not isinstance(step.get("verifiableOutcome"), str) or not step.get("verifiableOutcome", "").strip():
            add_issue(failures, "orphan_step", f"{path}/verifiableOutcome", "step requires a verifiableOutcome")
    if not roots:
        add_issue(failures, "orphan_step", "/steps", "at least one goal-edge/root step with no dependsOnSteps is required")
    if not terminal_ids:
        add_issue(failures, "orphan_step", "/steps", "at least one terminal step is required")
    reachable: set[str] = set()
    stack = list(roots)
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(children.get(current, set()))
    for step_id in ids:
        if step_id not in reachable:
            add_issue(failures, "orphan_step", f"/steps/{step_id}", "step is not reachable from a goal-edge/root")
    reverse_children = {step_id: set() for step_id in ids}
    for parent, child_ids in children.items():
        for child in child_ids:
            reverse_children.setdefault(child, set()).add(parent)
    can_reach_terminal: set[str] = set()
    stack = list(terminal_ids)
    while stack:
        current = stack.pop()
        if current in can_reach_terminal:
            continue
        can_reach_terminal.add(current)
        stack.extend(reverse_children.get(current, set()))
    for step_id in ids:
        if step_id not in can_reach_terminal:
            add_issue(failures, "orphan_step", f"/steps/{step_id}", "step is not on a path to a terminal step")
    return {"steps": steps, "terminalStepIds": terminal_ids, "rootStepIds": roots}


def compute_report(project: Path, plan: str) -> dict[str, Any]:
    directory = plan_dir(project, plan)
    context = json_load(directory / "context.json")
    brief = (directory / "brief.txt").read_text(encoding="utf-8")
    intake = json_load(directory / "intake.json")
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    elements_raw = intake_elements(intake)
    questions = intake.get("questions", [])
    if not isinstance(questions, list):
        add_issue(failures, "question_without_resolution", "/questions", "questions must be a list")
        questions = []
    question_map = {question_id(q, i): q for i, q in enumerate(questions) if isinstance(q, dict)}
    findings_raw = intake.get("findings", [])
    if not isinstance(findings_raw, list):
        findings_raw = []
    finding_reports: list[dict[str, Any]] = []
    finding_ids: set[str] = set()
    for index, finding in enumerate(findings_raw):
        if not isinstance(finding, dict):
            continue
        fid = finding_id(finding, index)
        finding_ids.add(fid)
        kind = finding_kind(finding)
        report_item = {"id": fid, "kind": kind, "citations": []}
        citations = citation_list_for_finding(finding)
        if kind == "contradiction" and len(citations) < 2:
            add_issue(
                failures,
                "citation_unverified",
                f"/findings/{index}/citations",
                "contradiction requires two verifying citations",
            )
        if kind == "solution-as-goal" and len(citations) != 1:
            add_issue(
                failures,
                "citation_unverified",
                f"/findings/{index}/citation",
                "solution-as-goal requires one verifying citation",
            )
        for citation_index, citation in enumerate(citations):
            ok, message = verify_offset_quote(brief, citation)
            citation_report = {"index": citation_index, "verified": ok, "message": message}
            if isinstance(citation, dict):
                citation_report.update(
                    {
                        "offset": citation.get("offset"),
                        "quote": citation_quote(citation),
                    }
                )
            report_item["citations"].append(citation_report)
            if not ok:
                add_issue(
                    failures,
                    "citation_unverified",
                    f"/findings/{index}/citations/{citation_index}",
                    message,
                )
        finding_reports.append(report_item)

    element_reports: list[dict[str, Any]] = []
    effective_dispositions: dict[str, str] = {}
    shape_forced_weak: set[str] = set()
    for element_id in RUBRIC_IDS:
        element = elements_raw.get(element_id)
        if not element:
            add_issue(
                failures,
                "rubric_element_unaccounted",
                f"/elements/{element_id}",
                "fixed rubric element has no disposition",
            )
            continue
        disposition = element.get("disposition")
        element_report: dict[str, Any] = {
            "id": element_id,
            "disposition": disposition,
            "effectiveDisposition": disposition,
            "citationVerified": None,
        }
        if disposition not in ALLOWED_DISPOSITIONS:
            add_issue(
                failures,
                "rubric_element_unaccounted",
                f"/elements/{element_id}/disposition",
                "disposition must be present, present-weak, or gap",
            )
            element_reports.append(element_report)
            continue
        if disposition in {"present", "present-weak"}:
            ok, message = verify_offset_quote(brief, element.get("citation"))
            element_report["citationVerified"] = ok
            element_report["citationMessage"] = message
            if isinstance(element.get("citation"), dict):
                element_report["citation"] = {
                    "offset": element["citation"].get("offset"),
                    "quote": citation_quote(element["citation"]),
                }
            if not ok:
                add_issue(failures, "citation_unverified", f"/elements/{element_id}/citation", message)
        if disposition == "present":
            validate_value_items(brief, element_id, element, failures, element_report)
            shape = RUBRIC_BY_ID[element_id].get("shape")
            if shape:
                reason = shape_failure(element_id, value_items_for(element))
                if reason:
                    shape_forced_weak.add(element_id)
                    element_report["effectiveDisposition"] = "present-weak"
                    element_report["shapeStatus"] = "fails"
                    element_report["shapeReason"] = reason
                    add_issue(
                        warnings,
                        "present_value_fails_shape",
                        f"/elements/{element_id}/valueItems",
                        reason,
                    )
        effective = element_report["effectiveDisposition"]
        effective_dispositions[element_id] = effective
        if effective == "gap":
            hits = indicator_terms_present(brief, element_id)
            if hits:
                add_issue(
                    warnings,
                    "gap_with_indicator_terms_present",
                    f"/elements/{element_id}",
                    "gap element has skill-fixed indicator terms present in the brief",
                    {"indicatorTerms": hits},
                )
        if effective in {"present-weak", "gap"}:
            deps = dependent_questions(element_id, element, [q for q in questions if isinstance(q, dict)])
            if effective == "gap" and has_model_default(element):
                element_report["questionRequired"] = False
                element_report["modelDefault"] = element.get("modelDefault", element.get("flaggedDefault"))
            elif not deps:
                add_issue(
                    failures,
                    "weak_or_gap_without_question",
                    f"/elements/{element_id}",
                    f"{effective} requires a dependent question",
                )
            else:
                element_report["questionRequired"] = True
                dep_ids: list[str] = []
                for question in deps:
                    dep_ids.append(question.get("id") if isinstance(question.get("id"), str) else "")
                element_report["questionIds"] = [qid for qid in dep_ids if qid]
                if not any(question_bound_to_element(question, element_id, element, effective) for question in deps):
                    add_issue(
                        failures,
                        "question_not_bound_to_element",
                        f"/elements/{element_id}",
                        "dependent question does not reference the weak span/value or missing element label",
                    )
        element_reports.append(element_report)

    known_refs: set[str] = set()
    for element_id in RUBRIC_IDS:
        known_refs.add(element_id)
        known_refs.add(f"element:{element_id}")
    for fid in finding_ids:
        known_refs.add(fid)
        known_refs.add(f"finding:{fid}")
    question_reports: list[dict[str, Any]] = []
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            add_issue(failures, "question_without_resolution", f"/questions/{index}", "question must be an object")
            continue
        qid = question_id(question, index)
        known_refs.add(qid)
        known_refs.add(f"question:{qid}")
        resolves_raw = question.get("resolves", [])
        if isinstance(resolves_raw, str):
            resolves = [resolves_raw]
        elif isinstance(resolves_raw, list):
            resolves = [ref for ref in resolves_raw if isinstance(ref, str)]
        else:
            resolves = []
        report_item = {"id": qid, "resolves": resolves, "hasPlanDelta": question_has_plan_delta(question)}
        if not resolves:
            add_issue(
                failures,
                "question_without_resolution",
                f"/questions/{index}/resolves",
                "question requires at least one resolves target",
            )
        for ref in resolves:
            if ref not in known_refs and ref_target_id(ref) not in known_refs:
                add_issue(
                    failures,
                    "question_without_resolution",
                    f"/questions/{index}/resolves",
                    f"unknown resolves target: {ref}",
                )
        if not question_has_plan_delta(question):
            add_issue(
                failures,
                "question_without_resolution",
                f"/questions/{index}/planDelta",
                "question requires planDelta, or every option requires planDelta",
            )
        question_reports.append(report_item)

    assumption_refs: set[str] = set(RUBRIC_IDS)
    assumption_refs.update(f"element:{element_id}" for element_id in RUBRIC_IDS)
    for fid in finding_ids:
        assumption_refs.add(fid)
        assumption_refs.add(f"finding:{fid}")
    for qid in question_map:
        assumption_refs.add(qid)
        assumption_refs.add(f"question:{qid}")
    step_report = validate_steps(intake, assumption_refs, failures)

    ok = not failures
    report = {
        "schema": REPORT_SCHEMA,
        "ok": ok,
        "finalizeAdmissible": ok,
        "generatedAt": utc_now(),
        "rubricId": context.get("rubricId", RUBRIC_ID),
        "briefSha256": sha256_text(brief),
        "intakeSha256": sha256_text(json.dumps(intake, ensure_ascii=False, sort_keys=True)),
        "failureCount": len(failures),
        "warningCount": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "rubric": {
            "requiredElements": RUBRIC_IDS,
            "accountedElements": sorted(elements_raw.keys() & set(RUBRIC_IDS)),
            "elements": element_reports,
        },
        "findings": finding_reports,
        "questions": question_reports,
        "steps": {
            "count": len(step_report["steps"]),
            "rootStepIds": step_report["rootStepIds"],
            "terminalStepIds": step_report["terminalStepIds"],
        },
        "statusGate": {
            "shapeForcedWeakElementIds": sorted(shape_forced_weak),
            "effectiveDispositions": effective_dispositions,
        },
    }
    json_dump(directory / "report.json", report)
    return report


def intake_summary_for_finalize(intake: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    elements_raw = intake_elements(intake)
    effective = report.get("statusGate", {}).get("effectiveDispositions", {})
    weak: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for element_id in RUBRIC_IDS:
        element = elements_raw.get(element_id, {})
        disposition = effective.get(element_id, element.get("disposition"))
        item = {
            "id": element_id,
            "label": RUBRIC_BY_ID[element_id]["label"],
            "disposition": disposition,
            "originalDisposition": element.get("disposition"),
        }
        if disposition == "present-weak":
            weak.append(item)
        if disposition == "gap":
            if has_model_default(element):
                item["modelDefault"] = element.get("modelDefault", element.get("flaggedDefault"))
            gaps.append(item)
    findings = intake.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    solution_as_goal = [finding for finding in findings if isinstance(finding, dict) and finding_kind(finding) == "solution-as-goal"]
    contradictions = [finding for finding in findings if isinstance(finding, dict) and finding_kind(finding) == "contradiction"]
    questions = intake.get("questions", [])
    if not isinstance(questions, list):
        questions = []
    return {
        "weakElements": weak,
        "gaps": gaps,
        "solutionAsGoalFindings": solution_as_goal,
        "contradictionFindings": contradictions,
        "questions": questions,
    }


def command_init(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    if args.rubric != RUBRIC_ID:
        raise SystemExit(f"Unsupported rubric id: {args.rubric}")
    brief, source = read_brief_from_args(args)
    digest = sha256_text(brief)
    directory = plan_dir(project, args.plan)
    context_path = directory / "context.json"
    if context_path.exists():
        context = json_load(context_path)
        existing = context.get("briefSha256")
        if existing != digest:
            fail(
                "brief_hash_changed",
                "Refusing to re-init an existing plan slug with a different brief hash",
                {"existingBriefSha256": existing, "newBriefSha256": digest},
            )
        print_json(
            {
                "ok": True,
                "idempotent": True,
                "planDir": str(directory),
                "briefSha256": digest,
                "rubricId": context.get("rubricId"),
            }
        )
        return
    ensure_gitignore(project)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "brief.txt").write_text(brief, encoding="utf-8")
    context = {
        "schema": CONTEXT_SCHEMA,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
        "briefSha256": digest,
        "briefBytes": len(brief.encode("utf-8", errors="replace")),
        "briefSource": source,
        "rubricId": RUBRIC_ID,
        "rubric": rubric_manifest(),
    }
    json_dump(context_path, context)
    print_json({"ok": True, "idempotent": False, "planDir": str(directory), "briefSha256": digest, "rubricId": RUBRIC_ID})


def command_check(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    report = compute_report(project, args.plan)
    print_json(
        {
            "ok": report["ok"],
            "failureCount": report["failureCount"],
            "warningCount": report["warningCount"],
            "failures": report["failures"],
            "warnings": report["warnings"],
            "report": str(plan_dir(project, args.plan) / "report.json"),
        }
    )
    if not report["ok"]:
        raise SystemExit(1)


def command_finalize(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    directory = plan_dir(project, args.plan)
    if args.unscopable:
        if not args.reason or not args.reason.strip():
            fail("missing_reason", "--unscopable requires --reason")
        context = json_load(directory / "context.json")
        plan = {
            "schema": PLAN_SCHEMA,
            "finishState": "unscopable",
            "rubricId": context.get("rubricId", RUBRIC_ID),
            "briefSha256": context.get("briefSha256"),
            "reason": args.reason,
            "steps": [],
        }
        intake_report = {
            "schema": INTAKE_REPORT_SCHEMA,
            "finishState": "unscopable",
            "generatedAt": utc_now(),
            "rubricId": context.get("rubricId", RUBRIC_ID),
            "briefSha256": context.get("briefSha256"),
            "reason": args.reason,
            "message": "Brief is not scoping-admissible for intake v1.",
        }
        json_dump(directory / "plan.json", plan)
        json_dump(directory / "intakeReport.json", intake_report)
        print_json({"ok": True, "finishState": "unscopable", "plan": str(directory / "plan.json"), "intakeReport": str(directory / "intakeReport.json")})
        return
    if args.reason:
        raise SystemExit("--reason is only valid with --unscopable")
    report = compute_report(project, args.plan)
    if not report["ok"]:
        print_json(
            {
                "ok": False,
                "failureKind": "finalize_blocked",
                "message": "check failures must be resolved before finalize",
                "failureCount": report["failureCount"],
                "failures": report["failures"],
                "report": str(directory / "report.json"),
            }
        )
        raise SystemExit(1)
    context = json_load(directory / "context.json")
    intake = json_load(directory / "intake.json")
    steps = intake.get("steps", [])
    questions = intake.get("questions", [])
    if not isinstance(steps, list):
        steps = []
    if not isinstance(questions, list):
        questions = []
    summary = intake_summary_for_finalize(intake, report)
    plan = {
        "schema": PLAN_SCHEMA,
        "finishState": "ready",
        "generatedAt": utc_now(),
        "rubricId": context.get("rubricId", RUBRIC_ID),
        "briefSha256": context.get("briefSha256"),
        "steps": steps,
        "questions": questions,
        "statusGate": report.get("statusGate", {}),
    }
    intake_report = {
        "schema": INTAKE_REPORT_SCHEMA,
        "finishState": "ready",
        "generatedAt": utc_now(),
        "rubricId": context.get("rubricId", RUBRIC_ID),
        "briefSha256": context.get("briefSha256"),
        "warnings": report["warnings"],
        **summary,
    }
    json_dump(directory / "plan.json", plan)
    json_dump(directory / "intakeReport.json", intake_report)
    print_json({"ok": True, "finishState": "ready", "plan": str(directory / "plan.json"), "intakeReport": str(directory / "intakeReport.json")})


def command_status(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    directory = plan_dir(project, args.plan)
    context_path = directory / "context.json"
    if not context_path.exists():
        print_json({"ok": True, "initialized": False, "planDir": str(directory)})
        return
    context = json_load(context_path)
    brief_path = directory / "brief.txt"
    current_hash = sha256_text(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else None
    report_path = directory / "report.json"
    report = json_load(report_path) if report_path.exists() else None
    print_json(
        {
            "ok": True,
            "initialized": True,
            "planDir": str(directory),
            "rubricId": context.get("rubricId"),
            "briefSha256": context.get("briefSha256"),
            "briefHashMatchesContext": current_hash == context.get("briefSha256"),
            "hasIntake": (directory / "intake.json").exists(),
            "hasReport": report_path.exists(),
            "reportOk": report.get("ok") if isinstance(report, dict) else None,
            "hasPlan": (directory / "plan.json").exists(),
            "hasIntakeReport": (directory / "intakeReport.json").exists(),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="techne intake brief gate")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--project", type=Path, required=True, help="target project root")
        sub.add_argument("--plan", required=True, help="plan slug under .techne/plan/")

    init = subparsers.add_parser("init", help="ingest a written brief")
    add_common(init)
    init.add_argument("--brief-file", help="brief file path, or '-' for stdin")
    init.add_argument("--brief-text", help="brief text supplied inline")
    init.add_argument("--rubric", default=RUBRIC_ID, help=f"rubric id (default: {RUBRIC_ID})")
    init.set_defaults(func=command_init)

    check = subparsers.add_parser("check", help="check intake.json against the brief and rubric")
    add_common(check)
    check.set_defaults(func=command_check)

    finalize = subparsers.add_parser("finalize", help="emit plan.json and intakeReport.json")
    add_common(finalize)
    finalize.add_argument("--unscopable", action="store_true", help="loud escape for unsupported/thin briefs")
    finalize.add_argument("--reason", help="required with --unscopable")
    finalize.set_defaults(func=command_finalize)

    status = subparsers.add_parser("status", help="show artifact status")
    add_common(status)
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

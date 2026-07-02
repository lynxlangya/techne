#!/usr/bin/env python3
"""Evidence gate for techne/diligence public-company research.

Python 3 stdlib only. POSIX developer environments only.

The gate writes dated evidence snapshots, verifies offset+quote citations,
computes evidence rungs, and refuses finalized reports whose dispositions outrun
their evidence. E2 is gate-fetched URL evidence. E1 is host-relayed evidence and
can never promote a disposition to present.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus, urljoin, urlsplit


SCOPE_SCHEMA = "techne.diligence.scope/1"
RESEARCH_SCHEMA = "techne.diligence.research/1"
REPORT_SCHEMA = "techne.diligence.report/1"
META_SCHEMA = "techne.diligence.reportMeta/1"
RUBRIC_ID = "public-company-deep-dive-v1"

MAX_SUMMARY_CHARS = 240
MAX_FETCH_BYTES = 2_000_000
MAX_REDIRECTS = 5
REFLECTION_THRESHOLD = 0.5
REFLECTION_MIN_QUOTE_TOKENS = 4
STEM_SUFFIXES = ("ing", "ies", "es", "ed", "s")
STEM_MIN_BASE_LEN = 3
FETCH_SPREAD_WARNING_SECONDS = 2 * 60 * 60
STALE_SOURCE_DAYS = {
    "price-trend": 14,
    "institutional-sentiment": 45,
    "ownership-structure": 120,
    "management": 365,
    "culture": 730,
}

RUBRIC: list[dict[str, Any]] = [
    {
        "id": "history-origin",
        "label": "History and origin",
        "definition": "Founding story, key milestones, and abandoned strategies or business lines.",
        "indicatorTerms": ["founded", "origin", "history", "milestone", "strategy", "abandoned", "discontinued"],
    },
    {
        "id": "business-model",
        "label": "Business model",
        "definition": "Revenue streams, unit economics, moat, and switching costs.",
        "indicatorTerms": ["revenue", "segment", "subscription", "margin", "unit economics", "moat", "switching"],
    },
    {
        "id": "financial-analysis-3yr",
        "label": "Financial analysis, three years",
        "definition": "Three-year revenue, margin, cash-flow, and balance-sheet trend.",
        "indicatorTerms": ["revenue", "gross margin", "operating margin", "cash flow", "debt", "balance sheet"],
    },
    {
        "id": "competitive-landscape",
        "label": "Competitive landscape",
        "definition": "Named competitors, positioning basis, and neutral comparison snapshot.",
        "indicatorTerms": ["competitor", "competition", "peer", "market share", "position", "compare"],
    },
    {
        "id": "management",
        "label": "Management",
        "definition": "Executives, background, tenure, and notable management changes.",
        "indicatorTerms": ["chief executive", "ceo", "management", "director", "officer", "tenure"],
    },
    {
        "id": "culture",
        "label": "Culture",
        "definition": "Stated values, founder communications, and credible third-party accounts.",
        "indicatorTerms": ["culture", "values", "employee", "founder letter", "mission", "workplace"],
    },
    {
        "id": "major-events",
        "label": "Major events",
        "definition": "M&A, leadership changes, restructurings, crises, IPOs, spin-offs, and abandoned strategies.",
        "indicatorTerms": ["acquisition", "merger", "ipo", "spin-off", "restructuring", "crisis", "leadership"],
    },
    {
        "id": "ownership-structure",
        "label": "Ownership structure",
        "definition": "Major shareholders and institutional holders.",
        "indicatorTerms": ["shareholder", "holder", "ownership", "institutional", "beneficial owner", "proxy"],
    },
    {
        "id": "institutional-sentiment",
        "label": "Institutional sentiment",
        "definition": "Analyst ratings, price targets, consensus, and institutional framing.",
        "indicatorTerms": ["analyst", "rating", "price target", "consensus", "institutional", "sentiment"],
    },
    {
        "id": "risk-factors",
        "label": "Risk factors",
        "definition": "Regulatory, competitive, operational, financial, and macro risks.",
        "indicatorTerms": ["risk", "regulatory", "competition", "operational", "financial", "macro"],
    },
    {
        "id": "ai-relevance",
        "label": "AI relevance",
        "definition": "Material AI exposure, or an evidenced no-material-link disposition.",
        "indicatorTerms": ["ai", "artificial intelligence", "machine learning", "accelerator", "gpu", "model"],
    },
    {
        "id": "price-trend",
        "label": "Price trend",
        "definition": "Qualitative price and volatility description.",
        "indicatorTerms": ["share price", "stock price", "volatility", "52 week", "market cap", "return"],
    },
]

RUBRIC_IDS = [item["id"] for item in RUBRIC]
RUBRIC_BY_ID = {item["id"]: item for item in RUBRIC}

ALLOWED_DISPOSITIONS = {"present", "present-weak", "gap", "no-material-link"}
AI_ONLY_DISPOSITION = "no-material-link"

SUBFACETS: dict[str, list[str]] = {
    "financial-analysis-3yr": [
        "revenue-trend",
        "margin-profitability-trend",
        "cash-flow-trend",
        "balance-sheet-health",
    ],
    "competitive-landscape": [
        "peer-identification",
        "positioning-basis",
        "comparison-snapshot",
    ],
    "business-model": [
        "revenue-streams",
        "unit-economics",
        "moat-or-switching-costs",
    ],
    "history-origin": ["abandonedStrategiesChecked"],
    "major-events": ["abandonedStrategiesChecked"],
}

RISK_CATEGORIES = {"regulatory", "competitive", "operational", "financial", "macro"}

SOURCE_CLASS_ALLOWLIST: dict[str, set[str]] = {
    "identity": {"identity-registry", "regulatory-filing", "exchange-listing", "company-ir"},
    "history-origin": {"regulatory-filing", "exchange-filing", "company-ir", "financial-news"},
    "business-model": {"regulatory-filing", "company-ir", "financial-news", "data-provider"},
    "financial-analysis-3yr": {"regulatory-filing", "company-ir", "market-data", "data-provider"},
    "competitive-landscape": {"regulatory-filing", "company-ir", "market-data", "data-provider", "financial-news"},
    "management": {"company-ir", "regulatory-filing", "exchange-filing", "financial-news"},
    "culture": {"company-ir", "financial-news", "third-party-research", "employee-review"},
    "major-events": {"regulatory-filing", "exchange-filing", "company-ir", "financial-news"},
    "ownership-structure": {"regulatory-filing", "proxy-filing", "shareholder-disclosure", "data-provider", "exchange-filing"},
    "institutional-sentiment": {"analyst-research", "market-data", "data-provider", "financial-news"},
    "risk-factors": {"regulatory-filing", "company-ir", "financial-news"},
    "ai-relevance": {"regulatory-filing", "company-ir", "product-disclosure", "financial-news", "data-provider"},
    "price-trend": {"market-data", "exchange-listing", "data-provider", "financial-news"},
}

GAP_SOURCE_CLASS_FLOORS: dict[str, set[str]] = {
    "history-origin": {"regulatory-filing", "company-ir"},
    "business-model": {"regulatory-filing", "company-ir"},
    "financial-analysis-3yr": {"regulatory-filing"},
    "competitive-landscape": {"regulatory-filing", "financial-news"},
    "management": {"company-ir", "regulatory-filing"},
    "culture": {"company-ir", "financial-news"},
    "major-events": {"regulatory-filing", "financial-news"},
    "ownership-structure": {"shareholder-disclosure", "proxy-filing"},
    "institutional-sentiment": {"analyst-research", "market-data"},
    "risk-factors": {"regulatory-filing"},
    "ai-relevance": {"regulatory-filing", "company-ir", "product-disclosure"},
    "price-trend": {"market-data"},
}

STOPLIST = {
    "a", "about", "above", "after", "again", "against", "all", "also", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "being", "between", "both",
    "by", "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
    "having", "if", "in", "into", "is", "it", "its", "may", "might", "more", "most",
    "must", "of", "on", "or", "our", "over", "per", "shall", "should", "so", "than",
    "that", "the", "their", "them", "then", "there", "these", "this", "those",
    "through", "to", "under", "use", "used", "using", "via", "was", "we", "were",
    "while", "will", "with", "would",
}

RUBRIC_LABEL_TOKENS = {
    "ai", "analysis", "analyst", "balance", "business", "cash", "category", "citation",
    "citations", "company", "competitive", "culture", "date", "deep", "diligence",
    "dive", "element", "elements", "evidence", "financial", "gap", "history", "identity",
    "institutional", "landscape", "major", "management", "market", "model", "origin",
    "ownership", "plain", "present", "price", "research", "risk", "risks", "sentiment",
    "source", "sources", "structure", "summary", "trend", "weak",
}

DERIVED_TREND_RE = re.compile(
    r"\b(?:accelerat(?:e|ed|ing)|decelerat(?:e|ed|ing)|improv(?:e|ed|ing)|"
    r"deteriorat(?:e|ed|ing)|grow(?:s|ing|th)?|declin(?:e|ed|ing)|trend(?:ed|ing)?|"
    r"increas(?:e|ed|ing)|decreas(?:e|ed|ing)|expand(?:ed|ing)?|contract(?:ed|ing)?)\b",
    re.IGNORECASE,
)

AI_INDICATOR_TERMS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "large language model",
    "generative ai",
    "accelerator",
    "gpu",
    "neural",
    "model training",
]

REVENUE_PRODUCT_SEGMENT_TERMS = [
    "revenue",
    "sales",
    "segment",
    "product",
    "platform",
    "service",
    "customer",
    "commercial",
]

REFLECTOR_HOST_RE = re.compile(
    r"(?:^|\.)(?:postman-echo\.com|httpbin\.org|webhook\.site|requestbin\.(?:com|net)|"
    r"pipedream\.net|beeceptor\.com|mocky\.io|ngrok-free\.app|localtunnel\.me)$",
    re.IGNORECASE,
)

REFLECTOR_PATH_RE = re.compile(
    r"(?:^|/)(?:echo|webhook|requestbin|debug|inspect|anything|mirror)(?:/|$)",
    re.IGNORECASE,
)

DATE_FIELD_ORDER = ("sourcePublishedAt", "filingDate", "periodEnd", "observedMarketDate", "capturedAt")

DOMAIN_SOURCE_CLASSES: list[tuple[str, set[str]]] = [
    ("sec.gov", {"identity-registry", "regulatory-filing", "exchange-filing"}),
    ("edgar-online.com", {"identity-registry", "regulatory-filing", "data-provider"}),
    ("nasdaq.com", {"identity-registry", "exchange-listing", "market-data", "data-provider", "financial-news"}),
    ("nyse.com", {"identity-registry", "exchange-listing", "market-data"}),
    ("hkexnews.hk", {"identity-registry", "exchange-listing", "exchange-filing", "regulatory-filing"}),
    ("hkex.com.hk", {"identity-registry", "exchange-listing", "exchange-filing"}),
    ("londonstockexchange.com", {"identity-registry", "exchange-listing", "market-data"}),
    ("jpx.co.jp", {"identity-registry", "exchange-listing", "exchange-filing"}),
    ("sse.com.cn", {"identity-registry", "exchange-listing", "exchange-filing"}),
    ("szse.cn", {"identity-registry", "exchange-listing", "exchange-filing"}),
    ("reuters.com", {"financial-news", "market-data", "data-provider"}),
    ("bloomberg.com", {"financial-news", "market-data", "data-provider"}),
    ("ft.com", {"financial-news"}),
    ("wsj.com", {"financial-news", "market-data"}),
    ("marketwatch.com", {"financial-news", "market-data", "data-provider"}),
    ("finance.yahoo.com", {"market-data", "data-provider", "financial-news"}),
    ("morningstar.com", {"market-data", "data-provider", "analyst-research"}),
    ("spglobal.com", {"market-data", "data-provider", "analyst-research"}),
    ("fitchratings.com", {"analyst-research", "data-provider"}),
    ("moodys.com", {"analyst-research", "data-provider"}),
    ("companiesmarketcap.com", {"market-data", "data-provider"}),
    ("macrotrends.net", {"market-data", "data-provider"}),
]


class CheckContext:
    def __init__(self, run_dir: Path, scope: dict[str, Any], research: dict[str, Any], sources: dict[str, dict[str, Any]]):
        self.run_dir = run_dir
        self.scope = scope
        self.research = research
        self.sources = sources
        self.events = load_events(run_dir)
        self.source_integrity_checked: set[str] = set()
        self.failures: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []
        self.citation_results: list[dict[str, Any]] = []
        self.element_results: dict[str, dict[str, Any]] = {}
        self.claim_tokens: dict[str, set[str]] = {}
        self.claim_dates: dict[str, list[str]] = {}
        self.grounded_values: list[dict[str, Any]] = []
        self.e1_citations: list[dict[str, Any]] = []

    def failure(self, code: str, message: str, **extra: Any) -> None:
        item = {"code": code, "message": message}
        item.update({k: v for k, v in extra.items() if v is not None})
        self.failures.append(item)

    def warning(self, code: str, message: str, **extra: Any) -> None:
        item = {"code": code, "message": message}
        item.update({k: v for k, v in extra.items() if v is not None})
        self.warnings.append(item)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def require_posix() -> None:
    if os.name != "posix":
        raise SystemExit("diligence_gate.py v1 supports POSIX developer environments only (macOS/Linux).")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip(".-_")
    return slug.upper() if slug else "TICKER"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


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


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


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


def base_dir(project: Path) -> Path:
    return project / ".techne" / "anchor-diligence"


def run_dir(project: Path, ticker: str) -> Path:
    return base_dir(project) / slugify(ticker)


def ensure_gitignore(project: Path) -> None:
    gitignore = project / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if ".techne/" not in [line.strip() for line in existing]:
        prefix = "" if not existing or existing[-1] == "" else "\n"
        with gitignore.open("a", encoding="utf-8") as handle:
            handle.write(f"{prefix}.techne/\n")


def append_event(directory: Path, event: dict[str, Any]) -> None:
    event = {"capturedAt": utc_now(), **event}
    path = directory / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def load_events(directory: Path) -> list[dict[str, Any]]:
    path = directory / "events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch if ch.isalnum() else " " for ch in value)


def content_tokens(value: str) -> list[str]:
    tokens = normalize_text(value).split()
    return [tok for tok in tokens if tok not in STOPLIST and tok not in RUBRIC_LABEL_TOKENS]


def token_set(value: str) -> set[str]:
    return set(content_tokens(value))


def stem(token: str) -> str:
    for suffix in STEM_SUFFIXES:
        # Length floor keeps short tokens (e.g. "as", "is") from collapsing
        # into near-empty stems that would then spuriously match each other.
        if token.endswith(suffix) and len(token) - len(suffix) >= STEM_MIN_BASE_LEN:
            base = token[: -len(suffix)]
            return base + "y" if suffix == "ies" else base
    return token


def stemmed_set(tokens: set[str]) -> set[str]:
    return {stem(tok) for tok in tokens}


def normalized_locator(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def parse_date(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    candidates = [raw]
    if raw.endswith("Z"):
        candidates.append(raw[:-1] + "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        candidates.append(raw + "T00:00:00+00:00")
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def admissible_snapshot_date(meta: dict[str, Any]) -> tuple[str | None, datetime | None]:
    for field in DATE_FIELD_ORDER:
        parsed = parse_date(meta.get(field))
        if parsed:
            return field, parsed
    return None, None


def validate_ip_literal(ip_text: str) -> tuple[bool, dict[str, Any]]:
    try:
        addr = ipaddress.ip_address(ip_text)
    except ValueError:
        return False, {"ip": ip_text, "error": "invalid_ip"}
    mapped = getattr(addr, "ipv4_mapped", None)
    addrs = [addr]
    if mapped is not None:
        addrs.append(mapped)
    details = []
    ok = True
    for candidate in addrs:
        flags = {
            "ip": str(candidate),
            "version": candidate.version,
            "is_global": candidate.is_global,
            "is_private": candidate.is_private,
            "is_multicast": candidate.is_multicast,
            "is_reserved": candidate.is_reserved,
            "is_loopback": candidate.is_loopback,
            "is_link_local": candidate.is_link_local,
            "is_unspecified": candidate.is_unspecified,
        }
        admissible = (
            candidate.is_global
            and not candidate.is_private
            and not candidate.is_multicast
            and not candidate.is_reserved
            and not candidate.is_loopback
            and not candidate.is_link_local
            and not candidate.is_unspecified
        )
        flags["admissible"] = admissible
        details.append(flags)
        ok = ok and admissible
    return ok, {"ip": ip_text, "checks": details}


def validate_resolved_host(host: str, port: int) -> tuple[list[str], list[dict[str, Any]]]:
    if not host:
        raise ValueError("missing host")
    host_lower = host.rstrip(".").casefold()
    if host_lower in {"localhost", "localhost.localdomain"} or host_lower.endswith(".local"):
        raise ValueError("host is local or mDNS")
    try:
        ascii_host = host_lower.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("host cannot be IDNA-encoded") from exc

    try:
        literal_ok, literal_detail = validate_ip_literal(ascii_host)
        if "error" not in literal_detail:
            if not literal_ok:
                raise ValueError(f"host literal is not public global unicast: {ascii_host}")
            return [ascii_host], [literal_detail]
    except ValueError:
        raise

    try:
        infos = socket.getaddrinfo(ascii_host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"host resolution failed: {exc}") from exc
    resolved: list[str] = []
    details: list[dict[str, Any]] = []
    for info in infos:
        ip_text = info[4][0]
        if ip_text in resolved:
            continue
        ok, detail = validate_ip_literal(ip_text)
        detail["host"] = ascii_host
        details.append(detail)
        if not ok:
            raise ValueError(f"resolved address is not public global unicast: {ip_text}")
        resolved.append(ip_text)
    if not resolved:
        raise ValueError("host resolved to no addresses")
    return resolved, details


def reject_reflector_url(url: str) -> None:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if REFLECTOR_HOST_RE.search(host):
        raise ValueError("named reflector/debug host rejected for E2")
    if REFLECTOR_PATH_RE.search(parsed.path):
        raise ValueError("named reflector/debug endpoint rejected for E2")


def scope_issuer_hosts(scope: dict[str, Any] | None) -> set[str]:
    if not scope:
        return set()
    identity = scope.get("identity")
    if not isinstance(identity, dict):
        return set()
    hosts = set()
    raw_hosts = identity.get("issuerHosts") or []
    if isinstance(raw_hosts, list):
        for item in raw_hosts:
            if isinstance(item, dict):
                value = item.get("value")
            else:
                value = item
            if isinstance(value, str) and value.strip():
                hosts.add(value.strip().rstrip(".").casefold())
    return hosts


def infer_source_classes_from_url(url: str, scope: dict[str, Any] | None = None) -> set[str]:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").rstrip(".").casefold()
    path = parsed.path.casefold()
    classes: set[str] = set()
    for domain, domain_classes in DOMAIN_SOURCE_CLASSES:
        if host == domain or host.endswith("." + domain):
            classes.update(domain_classes)
    issuer_match = host in scope_issuer_hosts(scope)
    if issuer_match:
        classes.update({"company-ir"})
    if classes:
        if re.search(r"/(?:investor|ir|investors|annual-report|financials?|governance|leadership|management|news|press)", path):
            classes.update({"company-ir", "product-disclosure"})
        if re.search(r"/(?:10-k|10-q|20-f|6-k|annual|quarterly|filing|filings|disclosure)", path):
            classes.update({"regulatory-filing", "exchange-filing"})
        if re.search(r"/(?:stock|quote|market|chart|price|historical|ratings?|analyst|holders?)", path):
            classes.update({"market-data", "data-provider"})
        if re.search(r"/(?:proxy|def14a|shareholder|ownership|holders?)", path):
            classes.update({"proxy-filing", "shareholder-disclosure"})
        if re.search(r"/(?:product|segment|platform|technology|ai|artificial-intelligence)", path):
            classes.update({"product-disclosure"})
    return classes


def request_target(parsed: Any) -> str:
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return path


def read_http_body(response: http.client.HTTPResponse) -> bytes:
    body = response.read(MAX_FETCH_BYTES + 1)
    if len(body) > MAX_FETCH_BYTES:
        raise ValueError(f"response exceeds max fetch bytes ({MAX_FETCH_BYTES})")
    return body


def fetch_once(url: str, timeout: float) -> tuple[int, dict[str, str], bytes, str, list[str], list[dict[str, Any]]]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError(f"scheme not allowed for E2: {parsed.scheme or '<missing>'}")
    if parsed.scheme == "http":
        warning = "http_url_warning"
    else:
        warning = ""
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no hostname")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    reject_reflector_url(url)
    resolved_ips, resolution_details = validate_resolved_host(host, port)
    connect_ip = resolved_ips[0]

    try:
        if parsed.scheme == "https":
            raw_sock = socket.create_connection((connect_ip, port), timeout=timeout)
            tls_sock = ssl.create_default_context().wrap_socket(raw_sock, server_hostname=host)
            conn: http.client.HTTPConnection = http.client.HTTPConnection(host, port, timeout=timeout)
            conn.sock = tls_sock
        else:
            conn = http.client.HTTPConnection(connect_ip, port, timeout=timeout)
        conn.putrequest("GET", request_target(parsed), skip_host=True, skip_accept_encoding=True)
        host_header = host if parsed.port is None else f"{host}:{port}"
        conn.putheader("Host", host_header)
        conn.putheader("User-Agent", "techne-diligence-gate/1.0 (+https://github.com/lynxlangya/techne)")
        conn.putheader("Accept", "text/plain,text/html,application/json,application/xhtml+xml,*/*;q=0.8")
        conn.putheader("Connection", "close")
        conn.endheaders()
        response = conn.getresponse()
        headers = {k.lower(): v for k, v in response.getheaders()}
        body = read_http_body(response)
        if warning:
            headers["x-techne-warning"] = warning
        return response.status, headers, body, host, resolved_ips, resolution_details
    finally:
        try:
            conn.close()
        except UnboundLocalError:
            pass


def fetch_url(url: str, timeout: float = 20.0) -> tuple[str, dict[str, Any]]:
    current = url
    redirects: list[dict[str, Any]] = []
    warnings: list[str] = []
    for redirect_count in range(MAX_REDIRECTS + 1):
        status, headers, body, host, resolved_ips, resolution_details = fetch_once(current, timeout)
        if headers.get("x-techne-warning"):
            warnings.append(headers["x-techne-warning"])
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("location")
            if not location:
                raise ValueError(f"redirect status {status} without Location")
            if redirect_count >= MAX_REDIRECTS:
                raise ValueError("too many redirects")
            next_url = urljoin(current, location)
            redirects.append({"from": current, "to": next_url, "status": status, "resolvedIps": resolved_ips})
            current = next_url
            continue
        content_type = headers.get("content-type", "")
        charset = "utf-8"
        match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
        if match:
            charset = match.group(1).strip("\"'")
        text = body.decode(charset, errors="replace")
        metadata = {
            "finalUrl": current,
            "httpStatus": status,
            "contentType": content_type,
            "resolvedHost": host,
            "resolvedIps": resolved_ips,
            "resolutionDetails": resolution_details,
            "redirects": redirects,
            "contentLength": len(body),
            "contentHash": sha256_bytes(body),
            "warnings": sorted(set(warnings)),
        }
        return text, metadata
    raise ValueError("too many redirects")


def url_component_tokens(url: str) -> set[str]:
    parsed = urlsplit(url)
    component = " ".join([parsed.path or "", parsed.query or "", parsed.fragment or ""])
    return set(content_tokens(unquote_plus(component)))


def reflection_coverage(quote: str, url: str) -> float:
    quote_tokens = set(content_tokens(quote))
    if not quote_tokens:
        return 0.0
    url_tokens = url_component_tokens(url)
    return len(quote_tokens & url_tokens) / len(quote_tokens)


def unique_source_filename(directory: Path, source_id: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", source_id.strip()).strip(".-_") or "source"
    if not stem.endswith(".txt"):
        stem += ".txt"
    candidate = stem
    index = 2
    while (directory / "sources" / candidate).exists() or (directory / "sources" / f"{candidate}.meta.json").exists():
        base = stem[:-4]
        candidate = f"{base}-{index}.txt"
        index += 1
    return candidate


def load_sources(directory: Path) -> dict[str, dict[str, Any]]:
    sources_dir = directory / "sources"
    sources: dict[str, dict[str, Any]] = {}
    manifest_path = sources_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json_load(manifest_path)
        for entry in manifest.get("sources", []):
            if isinstance(entry, dict) and entry.get("file"):
                sources[entry["file"]] = entry
    if sources_dir.exists():
        for meta_path in sources_dir.glob("*.meta.json"):
            meta = json_load(meta_path)
            file_name = meta.get("file") or meta_path.name.removesuffix(".meta.json")
            sources[file_name] = {**sources.get(file_name, {}), **meta, "file": file_name}
    return sources


def write_source(directory: Path, file_name: str, text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    sources_dir = directory / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    content_bytes = text.encode("utf-8", errors="replace")
    path = sources_dir / file_name
    path.write_text(text, encoding="utf-8")
    meta = {
        **metadata,
        "file": file_name,
        "capturedAt": utc_now(),
        "contentHash": sha256_bytes(content_bytes),
        "contentLength": len(content_bytes),
    }
    json_dump(sources_dir / f"{file_name}.meta.json", meta)
    manifest_path = sources_dir / "manifest.json"
    manifest = json_load(manifest_path) if manifest_path.exists() else {"schema": "techne.diligence.sources/1", "sources": []}
    manifest["sources"] = [entry for entry in manifest.get("sources", []) if entry.get("file") != file_name]
    manifest["sources"].append(meta)
    json_dump(manifest_path, manifest)
    return meta


def source_has_event(ctx: CheckContext, file_name: str, meta: dict[str, Any]) -> bool:
    content_hash = meta.get("contentHash")
    rung = meta.get("rung")
    for event in ctx.events:
        if event.get("action") not in {"snapshot", "init"}:
            continue
        if event.get("contentHash") != content_hash:
            continue
        if event.get("rung") and event.get("rung") != rung:
            continue
        if event.get("file") == file_name or event.get("identityFile") == file_name:
            return True
    return False


def check_source_integrity(ctx: CheckContext, file_name: str, meta: dict[str, Any]) -> None:
    if file_name in ctx.source_integrity_checked:
        return
    ctx.source_integrity_checked.add(file_name)
    path = ctx.run_dir / "sources" / file_name
    if not path.exists():
        ctx.failure("citation_targets_unsaved_source", "Citation source file is missing", file=file_name)
        return
    raw = path.read_bytes()
    actual_hash = sha256_bytes(raw)
    if meta.get("contentHash") != actual_hash or meta.get("contentLength") not in {len(raw), None}:
        ctx.failure("source_hash_mismatch", "Source metadata hash/length does not match saved bytes", file=file_name)
    if not source_has_event(ctx, file_name, meta):
        ctx.failure("source_provenance_unverified", "Source has no matching gate event", file=file_name)
    rung = meta.get("rung")
    if rung == "E2":
        if meta.get("retrievalMethod") != "gate-url-fetch":
            ctx.failure("source_provenance_unverified", "E2 source must be gate-url-fetch", file=file_name)
        final_url = str(meta.get("finalUrl") or meta.get("sourceLocator") or "")
        parsed = urlsplit(final_url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            ctx.failure("source_provenance_unverified", "E2 source must record a network finalUrl", file=file_name)
        if isinstance(meta.get("httpStatus"), int) and meta["httpStatus"] >= 400:
            ctx.failure("source_provenance_unverified", "E2 source recorded an HTTP error status", file=file_name, httpStatus=meta["httpStatus"])
        resolved_ips = meta.get("resolvedIps")
        if not isinstance(resolved_ips, list) or not resolved_ips:
            ctx.failure("source_provenance_unverified", "E2 source must record resolved IPs", file=file_name)
        else:
            for ip_text in resolved_ips:
                ok, _detail = validate_ip_literal(str(ip_text))
                if not ok:
                    ctx.failure("source_provenance_unverified", "E2 source recorded a non-admissible resolved IP", file=file_name, ip=str(ip_text))
    elif rung == "E1":
        if not meta.get("sourceLocator") or not meta.get("retrievalMethod"):
            ctx.failure("source_provenance_unverified", "E1 source must record sourceLocator and retrievalMethod", file=file_name)
    else:
        ctx.failure("source_provenance_unverified", "Source rung must be E1 or E2", file=file_name, rung=rung)


def verify_citation(ctx: CheckContext, citation: dict[str, Any], element_id: str, claim_id: str | None = None) -> dict[str, Any]:
    file_name = citation.get("file") or citation.get("source")
    result: dict[str, Any] = {
        "element": element_id,
        "claimId": claim_id,
        "file": file_name,
        "verified": False,
        "effectiveRung": None,
    }
    if not file_name or not isinstance(file_name, str):
        ctx.failure("citation_unverified", "Citation is missing file", element=element_id, claimId=claim_id)
        ctx.citation_results.append(result)
        return result
    meta = ctx.sources.get(file_name)
    if not meta:
        ctx.failure("citation_targets_unsaved_source", "Citation targets an unsaved source", element=element_id, file=file_name, claimId=claim_id)
        ctx.citation_results.append(result)
        return result
    check_source_integrity(ctx, file_name, meta)
    path = ctx.run_dir / "sources" / file_name
    if not path.exists():
        ctx.failure("citation_targets_unsaved_source", "Citation source file is missing", element=element_id, file=file_name, claimId=claim_id)
        ctx.citation_results.append(result)
        return result
    text = path.read_text(encoding="utf-8", errors="replace")
    offset = citation.get("offset")
    quote = citation.get("quote")
    if not isinstance(offset, int) or not isinstance(quote, str):
        ctx.failure("citation_unverified", "Citation needs integer offset and string quote", element=element_id, file=file_name, claimId=claim_id)
        ctx.citation_results.append(result)
        return result
    if offset < 0 or offset + len(quote) > len(text) or text[offset : offset + len(quote)] != quote:
        ctx.failure("citation_unverified", "Citation offset/quote does not match saved snapshot", element=element_id, file=file_name, claimId=claim_id)
        ctx.citation_results.append(result)
        return result

    rung = meta.get("rung")
    effective = rung if rung in {"E1", "E2"} else "E1"
    source_class = meta.get("sourceClass")
    if effective == "E2":
        allowed = SOURCE_CLASS_ALLOWLIST.get(element_id, set())
        inferred_classes = infer_source_classes_from_url(str(meta.get("finalUrl") or meta.get("sourceLocator") or ""), ctx.scope)
        result["verifiedSourceClasses"] = sorted(inferred_classes)
        if source_class not in allowed or source_class not in inferred_classes:
            ctx.failure(
                "e2_source_class_not_allowlisted",
                "E2 citation source class is not both allowlisted for this element and verified from its URL",
                element=element_id,
                file=file_name,
                sourceClass=source_class,
                verifiedSourceClasses=sorted(inferred_classes),
            )
            effective = "E1"
        locator = meta.get("finalUrl") or meta.get("sourceLocator") or ""
        coverage = reflection_coverage(quote, locator)
        result["reflectionCoverage"] = coverage
        quote_token_count = len(content_tokens(quote))
        result["reflectionExempt"] = quote_token_count < REFLECTION_MIN_QUOTE_TOKENS
        if quote_token_count >= REFLECTION_MIN_QUOTE_TOKENS and coverage >= REFLECTION_THRESHOLD:
            ctx.warning(
                "e2_reflection_downgrade",
                "Citation quote is substantially covered by the model-supplied URL path/query/fragment",
                element=element_id,
                file=file_name,
                coverage=round(coverage, 4),
            )
            effective = "E1"

    _, citation_date = admissible_snapshot_date(meta)
    as_of = parse_date(ctx.scope.get("analysisAsOf"))
    if as_of and citation_date and citation_date > as_of:
        ctx.failure(
            "citation_after_analysis_asof",
            "Citation date is after analysisAsOf in backtest mode",
            element=element_id,
            file=file_name,
            citationDate=citation_date.isoformat(),
            analysisAsOf=as_of.isoformat(),
        )

    result.update(
        {
            "verified": True,
            "quote": quote,
            "sourceClass": source_class,
            "declaredRung": rung,
            "effectiveRung": effective,
            "sourceLocator": meta.get("sourceLocator"),
            "contentHash": meta.get("contentHash"),
        }
    )
    if effective == "E1":
        ctx.e1_citations.append(result)
    ctx.citation_results.append(result)
    return result


def verify_citations(ctx: CheckContext, citations: Any, element_id: str, claim_id: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(citations, list) or not citations:
        ctx.failure("citation_unverified", "Expected a non-empty citations array", element=element_id, claimId=claim_id)
        return []
    return [verify_citation(ctx, citation, element_id, claim_id) for citation in citations if isinstance(citation, dict)]


def claim_item_id(item: dict[str, Any], index: int) -> str:
    return str(item.get("id") or f"claim-{index + 1}")


def check_claim_item(ctx: CheckContext, item: dict[str, Any], element_id: str, index: int) -> dict[str, Any]:
    cid = claim_item_id(item, index)
    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        ctx.failure("claim_item_missing_text", "Claim item needs text", element=element_id, claimId=cid)
        return {"id": cid, "computedDisposition": "gap", "tokens": []}
    citation_results = verify_citations(ctx, item.get("citations"), element_id, cid)
    verified_quotes = [result.get("quote", "") for result in citation_results if result.get("verified")]
    tokens = set(content_tokens(text))
    if not tokens:
        ctx.failure("claim_item_without_content_tokens", "Claim item has no content tokens after normalization", element=element_id, claimId=cid)
    stemmed_tokens = stemmed_set(tokens)
    if tokens and not any(stemmed_tokens <= stemmed_set(set(content_tokens(quote))) for quote in verified_quotes):
        ctx.failure(
            "claim_item_not_grounded_in_citation",
            "No single verified citation span grounds all claim item content tokens",
            element=element_id,
            claimId=cid,
        )
    if DERIVED_TREND_RE.search(text) and not item.get("derivedFrom"):
        dated = 0
        for result in citation_results:
            meta = ctx.sources.get(result.get("file") or "", {})
            _, parsed = admissible_snapshot_date(meta)
            if parsed or re.search(r"\b20\d{2}\b", result.get("quote", "")):
                dated += 1
        if dated < 2:
            ctx.failure(
                "derived_claim_without_basis",
                "Derived/trend claim needs derivedFrom or at least two dated grounding citations",
                element=element_id,
                claimId=cid,
            )
    effective_rungs = {result.get("effectiveRung") for result in citation_results if result.get("verified")}
    if "E1" in effective_rungs:
        computed = "present-weak"
    elif "E2" in effective_rungs:
        computed = "present"
    else:
        computed = "gap"
    ctx.claim_tokens[f"{element_id}:{cid}"] = tokens
    ctx.claim_dates[f"{element_id}:{cid}"] = [
        (admissible_snapshot_date(ctx.sources.get(result.get("file") or "", {}))[1] or datetime.min.replace(tzinfo=timezone.utc)).isoformat()
        for result in citation_results
        if result.get("verified")
    ]
    value_key = item.get("valueKey") or item.get("metric")
    value = item.get("value")
    if value_key is not None and value is not None:
        dates = []
        for result in citation_results:
            meta = ctx.sources.get(result.get("file") or "", {})
            _, parsed = admissible_snapshot_date(meta)
            if parsed:
                dates.append(parsed.isoformat())
        ctx.grounded_values.append(
            {
                "element": element_id,
                "key": str(value_key),
                "value": str(value),
                "claimId": cid,
                "dates": sorted(dates),
            }
        )
    return {"id": cid, "computedDisposition": computed, "tokens": sorted(tokens), "citationResults": citation_results}


def check_plain_summary(ctx: CheckContext, node: dict[str, Any], element_id: str, available_tokens: set[str]) -> None:
    disposition = node.get("disposition")
    if disposition not in {"present", "present-weak", "no-material-link"}:
        return
    summary = node.get("plainSummary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > MAX_SUMMARY_CHARS:
        ctx.failure("present_without_summary", "Evidence-bearing disposition needs a plainSummary within the length cap", element=element_id)
        return
    summary_tokens = set(content_tokens(summary))
    available_stems = stemmed_set(available_tokens)
    extras = sorted(tok for tok in summary_tokens if stem(tok) not in available_stems)
    if extras:
        ctx.failure(
            "plain_summary_introduces_ungrounded_content",
            "plainSummary introduces content absent from grounded claimItems",
            element=element_id,
            tokens=extras,
        )


def check_gap(ctx: CheckContext, node: dict[str, Any], element_id: str) -> None:
    if not isinstance(node.get("reason"), str) or not node.get("reason", "").strip():
        ctx.failure("gap_without_reasoning", "gap disposition needs reasoning", element=element_id)
    ledger = node.get("searchLedger")
    if not isinstance(ledger, dict):
        ctx.failure("gap_without_search_ledger", "gap disposition needs searchLedger", element=element_id)
        return
    checked = set()
    for value in ledger.get("sourceClassesChecked", []):
        if isinstance(value, str):
            checked.add(value)
    for query in ledger.get("queries", []):
        if isinstance(query, dict) and isinstance(query.get("sourceClass"), str):
            checked.add(query["sourceClass"])
    if not checked:
        ctx.failure("gap_without_search_ledger", "gap searchLedger names no checked source classes", element=element_id)
    floor = GAP_SOURCE_CLASS_FLOORS.get(element_id, set())
    missing = sorted(floor - checked)
    if missing:
        ctx.failure("gap_below_source_class_floor", "gap searchLedger is below source-class floor", element=element_id, missingSourceClasses=missing)


def saved_snapshot_texts(ctx: CheckContext) -> list[str]:
    values: list[str] = []
    for file_name in ctx.sources:
        path = ctx.run_dir / "sources" / file_name
        if path.exists():
            values.append(path.read_text(encoding="utf-8", errors="replace"))
    return values


def check_gap_indicator_warning(ctx: CheckContext, element_id: str) -> None:
    terms = RUBRIC_BY_ID[element_id].get("indicatorTerms", [])
    haystacks = [normalize_text(value) for value in saved_snapshot_texts(ctx)]
    for term in terms:
        norm = normalize_text(term).strip()
        if norm and any(norm in haystack for haystack in haystacks):
            ctx.warning("gap_with_indicator_terms_present", "Saved snapshots contain indicator terms for a gapped element", element=element_id, term=term)
            return


def check_no_material_link(ctx: CheckContext, node: dict[str, Any], element_id: str) -> set[str]:
    surfaces = node.get("checkedSurfaces")
    tokens: set[str] = set()
    if not isinstance(surfaces, list) or not surfaces:
        ctx.failure("no_material_link_without_checked_surfaces", "no-material-link needs checkedSurfaces", element=element_id)
        return tokens
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict):
            ctx.failure("no_material_link_without_checked_surfaces", "checkedSurface must be an object", element=element_id, index=index)
            continue
        for result in verify_citations(ctx, surface.get("citations"), element_id, f"checkedSurface-{index + 1}"):
            if result.get("verified"):
                tokens.update(content_tokens(result.get("quote", "")))
    for text in saved_snapshot_texts(ctx):
        norm = normalize_text(text)
        if any(normalize_text(ai).strip() in norm for ai in AI_INDICATOR_TERMS) and any(
            normalize_text(term).strip() in norm for term in REVENUE_PRODUCT_SEGMENT_TERMS
        ):
            ctx.warning(
                "no_material_link_indicator_conflict",
                "AI indicator terms co-occur with revenue/product/segment terms in saved snapshots",
                element=element_id,
            )
            return tokens
    return tokens


def aggregate_disposition(claim_results: list[dict[str, Any]]) -> str:
    if not claim_results:
        return "gap"
    dispositions = {item.get("computedDisposition") for item in claim_results}
    if "gap" in dispositions:
        return "gap"
    if "present-weak" in dispositions:
        return "present-weak"
    return "present"


def weakest_disposition(dispositions: list[str]) -> str:
    if not dispositions:
        return "gap"
    if "gap" in dispositions:
        return "gap"
    if "present-weak" in dispositions:
        return "present-weak"
    return "present"


def check_comparison_snapshot(ctx: CheckContext, node: dict[str, Any], element_id: str) -> None:
    snapshot = node.get("comparisonSnapshot")
    if not snapshot:
        ctx.failure("comparison_snapshot_uncited", "competitive-landscape present needs a comparisonSnapshot", element=element_id)
        return
    cells: list[dict[str, Any]] = []
    if isinstance(snapshot, list):
        for row in snapshot:
            if isinstance(row, dict):
                for key, value in row.items():
                    if isinstance(value, dict):
                        cells.append(value)
    elif isinstance(snapshot, dict):
        for row in snapshot.get("rows", []):
            if isinstance(row, dict):
                for value in row.values():
                    if isinstance(value, dict):
                        cells.append(value)
        for cell in snapshot.get("cells", []):
            if isinstance(cell, dict):
                cells.append(cell)
    if not cells:
        ctx.failure("comparison_snapshot_uncited", "comparisonSnapshot has no cited cells", element=element_id)
        return
    for index, cell in enumerate(cells):
        if not cell.get("citations"):
            ctx.failure("comparison_snapshot_uncited", "comparisonSnapshot cell lacks citations", element=element_id, index=index)
        else:
            verify_citations(ctx, cell.get("citations"), element_id, f"comparison-cell-{index + 1}")


def check_risk_items(ctx: CheckContext, node: dict[str, Any], element_id: str) -> None:
    items = node.get("riskItems")
    if not isinstance(items, list) or not items:
        ctx.failure("risk_item_missing_category", "risk-factors needs riskItems with fixed category tags", element=element_id)
        return
    for index, item in enumerate(items):
        if not isinstance(item, dict) or item.get("category") not in RISK_CATEGORIES:
            ctx.failure("risk_item_missing_category", "risk item category must be fixed tag", element=element_id, index=index)


def check_evidence_node(
    ctx: CheckContext,
    node: dict[str, Any],
    element_id: str,
    *,
    require_summary: bool = True,
    subfacet_results: dict[str, Any] | None = None,
    subfacet_tokens: set[str] | None = None,
) -> dict[str, Any]:
    disposition = node.get("disposition")
    if disposition not in ALLOWED_DISPOSITIONS:
        ctx.failure("invalid_disposition", "Unknown disposition", element=element_id, disposition=disposition)
        return {"declaredDisposition": disposition, "computedDisposition": "gap", "claimResults": [], "tokens": []}
    if disposition == AI_ONLY_DISPOSITION and element_id != "ai-relevance":
        ctx.failure("invalid_disposition", "no-material-link is only valid for ai-relevance", element=element_id)

    if disposition == "gap":
        check_gap(ctx, node, element_id)
        check_gap_indicator_warning(ctx, element_id)
        return {"declaredDisposition": disposition, "computedDisposition": "gap", "claimResults": [], "tokens": []}

    claim_items = node.get("claimItems")
    claim_results: list[dict[str, Any]] = []
    if isinstance(claim_items, list):
        for index, item in enumerate(claim_items):
            if isinstance(item, dict):
                claim_results.append(check_claim_item(ctx, item, element_id, index))
            else:
                ctx.failure("claim_item_missing_text", "claimItems must be objects", element=element_id, index=index)
    elif node.get("subfacets") and disposition in {"present", "present-weak"}:
        claim_items = []
    else:
        ctx.failure("claim_items_missing", "Evidence-bearing disposition needs claimItems", element=element_id)

    components: list[str] = []
    if claim_results:
        components.append(aggregate_disposition(claim_results))
    if subfacet_results:
        components.append(weakest_disposition([str(result.get("computedDisposition") or "gap") for result in subfacet_results.values()]))
    computed = weakest_disposition(components)
    tokens: set[str] = set()
    for result in claim_results:
        tokens.update(result.get("tokens", []))
    if subfacet_tokens:
        tokens.update(subfacet_tokens)

    if disposition == "present" and computed != "present":
        if computed == "present-weak":
            ctx.failure("present_disposition_contains_e1_claimitem", "present requires every claimItem to independently carry E2", element=element_id)
        else:
            ctx.failure("present_without_e2_claimitems", "present requires E2-grounded claimItems", element=element_id)
    if disposition == "present-weak" and computed == "gap":
        ctx.failure("present_weak_without_citation", "present-weak requires cited claimItems", element=element_id)

    if disposition == "no-material-link":
        tokens.update(check_no_material_link(ctx, node, element_id))

    if require_summary:
        check_plain_summary(ctx, node, element_id, tokens)

    return {
        "declaredDisposition": disposition,
        "computedDisposition": computed,
        "claimResults": claim_results,
        "tokens": sorted(tokens),
    }


def check_subfacets(ctx: CheckContext, element_id: str, node: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    required = SUBFACETS.get(element_id, [])
    if not required:
        return {}, set()
    subfacets = node.get("subfacets")
    if not isinstance(subfacets, dict):
        ctx.failure("subfacet_unaccounted", "Compound element needs subfacets", element=element_id, missingSubfacets=required)
        return {}, set()
    results: dict[str, Any] = {}
    aggregate_tokens: set[str] = set()
    for subfacet_id in required:
        child = subfacets.get(subfacet_id)
        if not isinstance(child, dict):
            ctx.failure("subfacet_unaccounted", "Required subfacet is missing", element=element_id, subfacet=subfacet_id)
            continue
        child_element_id = element_id
        result = check_evidence_node(ctx, child, child_element_id, require_summary=False)
        results[subfacet_id] = result
        aggregate_tokens.update(result.get("tokens", []))
        if child.get("disposition") == "present" and result.get("computedDisposition") != "present":
            ctx.failure("subfacet_present_not_e2_grounded", "present subfacet is not fully E2-grounded", element=element_id, subfacet=subfacet_id)
    if node.get("disposition") == "present":
        weak = [sf for sf, result in results.items() if result.get("computedDisposition") != "present"]
        if weak:
            ctx.failure("parent_present_with_weak_subfacet", "parent present requires every required subfacet present", element=element_id, weakSubfacets=weak)
    return results, aggregate_tokens


def check_element(ctx: CheckContext, element_id: str, node: Any) -> None:
    if not isinstance(node, dict):
        ctx.failure("rubric_element_unaccounted", "Rubric element is not an object", element=element_id)
        return
    subfacet_results, subfacet_tokens = check_subfacets(ctx, element_id, node)
    result = check_evidence_node(ctx, node, element_id, subfacet_results=subfacet_results, subfacet_tokens=subfacet_tokens)
    if element_id == "competitive-landscape" and node.get("disposition") == "present":
        check_comparison_snapshot(ctx, node, element_id)
    if element_id == "risk-factors" and node.get("disposition") in {"present", "present-weak"}:
        check_risk_items(ctx, node, element_id)
    ctx.element_results[element_id] = {**result, "subfacets": subfacet_results}


def identity_field_value(identity: dict[str, Any], field: str) -> str:
    value = identity.get(field)
    if isinstance(value, dict):
        return str(value.get("value") or "")
    return str(value or "")


def identity_field_citations(identity: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = identity.get(field)
    if isinstance(value, dict) and isinstance(value.get("citations"), list):
        return value["citations"]
    return []


def check_identity(ctx: CheckContext) -> None:
    identity = ctx.scope.get("identity")
    if not isinstance(identity, dict) or not identity.get("resolved"):
        ctx.failure("identity_unresolved", "scope.json has no resolved identity")
        return
    required = ["legalName", "ticker", "exchange"]
    if identity_field_value(identity, "identifier"):
        required.append("identifier")
    for field in required:
        if not identity_field_value(identity, field):
            ctx.failure("identity_unresolved", "identity field is empty", field=field)
            continue
        results = verify_citations(ctx, identity_field_citations(identity, field), "identity", f"identity-{field}")
        if not results or not any(result.get("effectiveRung") == "E2" for result in results):
            ctx.failure("identity_uncited", "identity field requires E2 citation", field=field)
    issuer_hosts = identity.get("issuerHosts") or []
    if isinstance(issuer_hosts, list):
        for index, item in enumerate(issuer_hosts):
            if not isinstance(item, dict) or not item.get("value"):
                ctx.failure("identity_uncited", "issuerHost entry needs a value", field=f"issuerHosts[{index}]")
                continue
            results = verify_citations(ctx, item.get("citations"), "identity", f"identity-issuerHost-{index + 1}")
            if not results or not any(result.get("effectiveRung") == "E2" for result in results):
                ctx.failure("identity_uncited", "issuerHost requires E2 citation", field=f"issuerHosts[{index}]")
    requested = identity.get("requested", {})
    requested_ticker = str(requested.get("ticker") or ctx.scope.get("ticker") or "").casefold()
    requested_exchange = str(requested.get("exchange") or ctx.scope.get("exchange") or "").casefold()
    if requested_ticker and identity_field_value(identity, "ticker").casefold() != requested_ticker:
        ctx.failure("identity_requested_mismatch", "resolved ticker does not exactly match requested ticker")
    if requested_exchange and identity_field_value(identity, "exchange").casefold() != requested_exchange:
        ctx.failure("identity_requested_mismatch", "resolved exchange does not exactly match requested exchange")


def check_fetch_spread_and_staleness(ctx: CheckContext) -> None:
    element_files: dict[str, set[str]] = {}
    for citation in ctx.citation_results:
        if citation.get("verified") and citation.get("element") in RUBRIC_IDS:
            element_files.setdefault(citation["element"], set()).add(citation["file"])
    all_dates: list[datetime] = []
    for citation in ctx.citation_results:
        meta = ctx.sources.get(citation.get("file") or "", {})
        parsed = parse_date(meta.get("capturedAt"))
        if parsed:
            all_dates.append(parsed)
    if all_dates:
        min_fetch, max_fetch = min(all_dates), max(all_dates)
        spread = (max_fetch - min_fetch).total_seconds()
        if spread > FETCH_SPREAD_WARNING_SECONDS:
            for element_id in ("price-trend", "institutional-sentiment"):
                if element_files.get(element_id):
                    ctx.warning(
                        "fetch_time_spread_exceeds_threshold",
                        "Fast-moving element citations are far apart in fetch time",
                        element=element_id,
                        spreadSeconds=int(spread),
                    )
    now = datetime.now(timezone.utc)
    for element_id, files in sorted(element_files.items()):
        dated: list[datetime] = []
        canonical = set()
        for file_name in files:
            meta = ctx.sources.get(file_name, {})
            field, parsed = admissible_snapshot_date(meta)
            if parsed:
                dated.append(parsed)
            canonical.add(f"{normalized_locator(str(meta.get('sourceLocator') or file_name))}\0{meta.get('contentHash')}")
        if len(canonical) == 1 and ctx.element_results.get(element_id, {}).get("declaredDisposition") == "present":
            ctx.warning("single_source_element", "Element is resolved from exactly one source identity", element=element_id)
        if dated:
            newest = max(dated)
            threshold_days = STALE_SOURCE_DAYS.get(element_id)
            if threshold_days and (now - newest).days > threshold_days:
                ctx.warning("stale_source", "Newest dated source is older than the element staleness threshold", element=element_id, daysOld=(now - newest).days)


def check_newer_conflicts(ctx: CheckContext) -> None:
    by_key: dict[tuple[str, str], dict[str, set[str]]] = {}
    for value in ctx.grounded_values:
        key = (value["element"], value["key"])
        bucket = by_key.setdefault(key, {})
        bucket.setdefault(value["value"], set()).update(value.get("dates") or [])
    for (element_id, key), values in by_key.items():
        if len(values) <= 1:
            continue
        dated_values = [dates for dates in values.values() if dates]
        if len(dated_values) >= 2:
            ctx.warning(
                "newer_contradictory_source_alarm",
                "Multiple differing grounded values exist for the same element/key",
                element=element_id,
                key=key,
                values=sorted(values),
            )


def e1_disclosure(ctx: CheckContext) -> list[dict[str, Any]]:
    by_claim: dict[str, list[dict[str, Any]]] = {}
    for citation in ctx.e1_citations:
        claim = f"{citation.get('element')}:{citation.get('claimId')}"
        by_claim.setdefault(claim, []).append(citation)
    output: list[dict[str, Any]] = []
    for claim, citations in sorted(by_claim.items()):
        canonical = {}
        for citation in citations:
            key = f"{normalized_locator(str(citation.get('sourceLocator') or citation.get('file') or ''))}\0{citation.get('contentHash') or ''}"
            canonical.setdefault(key, []).append(citation)
        snippets = len(citations)
        independent = len(canonical)
        note = f"{independent} independent E1 source"
        if independent != 1:
            note += "s"
        if snippets != independent:
            note += f" ({snippets} relayed snippets)"
        output.append({"claim": claim, "independentSources": independent, "relayedSnippets": snippets, "note": note})
    return output


def run_check(directory: Path) -> dict[str, Any]:
    scope = json_load(directory / "scope.json")
    research_path = directory / "research.json"
    research = json_load(research_path) if research_path.exists() else {"schema": RESEARCH_SCHEMA, "elements": {}}
    sources = load_sources(directory)
    ctx = CheckContext(directory, scope, research, sources)
    check_identity(ctx)
    elements = research.get("elements")
    if not isinstance(elements, dict):
        ctx.failure("rubric_element_unaccounted", "research.json needs elements object")
        elements = {}
    for element_id in RUBRIC_IDS:
        if element_id not in elements:
            ctx.failure("rubric_element_unaccounted", "Rubric element is missing", element=element_id)
            continue
        check_element(ctx, element_id, elements[element_id])
    check_fetch_spread_and_staleness(ctx)
    check_newer_conflicts(ctx)
    meta = {
        "schema": META_SCHEMA,
        "generatedAt": utc_now(),
        "warnings": ctx.warnings,
        "e1Disclosure": e1_disclosure(ctx),
        "citationResults": ctx.citation_results,
    }
    report = {
        "schema": REPORT_SCHEMA,
        "ok": not ctx.failures,
        "generatedAt": utc_now(),
        "rubricId": RUBRIC_ID,
        "failures": ctx.failures,
        "warnings": ctx.warnings,
        "elementResults": ctx.element_results,
        "citationResults": ctx.citation_results,
        "reportMeta": meta,
    }
    json_dump(directory / "report.json", report)
    json_dump(directory / "reportMeta.json", meta)
    return report


def find_quote(text: str, needle: str) -> dict[str, Any] | None:
    index = text.casefold().find(needle.casefold())
    if index < 0:
        return None
    return {"offset": index, "quote": text[index : index + len(needle)]}


def cmd_init(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    ticker = slugify(args.ticker)
    directory = run_dir(project, ticker)
    if directory.exists() and (directory / "scope.json").exists() and not args.force:
        fail("scope_exists", f"scope.json already exists for {ticker}; pass --force to replace")
    ensure_gitignore(project)
    directory.mkdir(parents=True, exist_ok=True)
    if not args.identity_url:
        fail("identity_unresolved", "init requires --identity-url for E2 identity evidence")
    try:
        text, fetch_meta = fetch_url(args.identity_url)
    except Exception as exc:
        fail("identity_unresolved", f"identity URL fetch refused or failed: {exc}")
    identity_file = unique_source_filename(directory, f"identity-{ticker}")
    inferred_classes = infer_source_classes_from_url(fetch_meta.get("finalUrl") or args.identity_url)
    identity_allowed = SOURCE_CLASS_ALLOWLIST["identity"]
    identity_source_class = next(
        (candidate for candidate in ("identity-registry", "regulatory-filing", "exchange-listing", "company-ir") if candidate in inferred_classes and candidate in identity_allowed),
        None,
    )
    if not identity_source_class:
        fail(
            "identity_unresolved",
            "identity URL did not verify into an identity-admissible source class",
            {"verifiedSourceClasses": sorted(inferred_classes)},
        )
    meta = write_source(
        directory,
        identity_file,
        text,
        {
            "rung": "E2",
            "retrievalMethod": "gate-url-fetch",
            "sourceLocator": args.identity_url,
            "sourceClass": identity_source_class,
            "verifiedSourceClasses": sorted(inferred_classes),
            **fetch_meta,
        },
    )
    fields = {
        "legalName": args.legal_name,
        "ticker": args.ticker,
        "exchange": args.exchange,
    }
    if args.identifier:
        fields["identifier"] = args.identifier
    identity: dict[str, Any] = {
        "resolved": True,
        "requested": {"ticker": args.ticker, "exchange": args.exchange, "companyName": args.legal_name},
    }
    for field, value in fields.items():
        citation = find_quote(text, value)
        if not citation:
            try:
                (directory / "scope.json").unlink()
            except FileNotFoundError:
                pass
            fail("identity_uncited", f"identity value not found in E2 identity source: {field}={value}")
        identity[field] = {"value": value, "citations": [{"file": identity_file, **citation}]}
    issuer_hosts = []
    for host in args.issuer_host or []:
        citation = find_quote(text, host)
        if not citation:
            fail("identity_uncited", f"issuer host not found in E2 identity source: {host}")
        issuer_hosts.append({"value": host.rstrip(".").casefold(), "citations": [{"file": identity_file, **citation}]})
    if issuer_hosts:
        identity["issuerHosts"] = issuer_hosts
    scope = {
        "schema": SCOPE_SCHEMA,
        "createdAt": utc_now(),
        "rubricId": RUBRIC_ID,
        "ticker": args.ticker,
        "exchange": args.exchange,
        "legalName": args.legal_name,
        "analysisAsOf": args.analysis_as_of,
        "identity": identity,
        "rubric": RUBRIC,
        "dispositions": sorted(ALLOWED_DISPOSITIONS),
        "sourceClassAllowlist": {key: sorted(value) for key, value in SOURCE_CLASS_ALLOWLIST.items()},
        "gapSourceClassFloors": {key: sorted(value) for key, value in GAP_SOURCE_CLASS_FLOORS.items()},
        "subfacets": SUBFACETS,
    }
    json_dump(directory / "scope.json", scope)
    append_event(directory, {"action": "init", "ticker": args.ticker, "identityFile": identity_file, "rung": "E2", "contentHash": meta["contentHash"]})
    print_json({"ok": True, "ticker": ticker, "directory": str(directory), "identityFile": identity_file})


def cmd_snapshot(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    directory = run_dir(project, args.ticker)
    if not (directory / "scope.json").exists():
        fail("identity_unresolved", "Run init before snapshot")
    ensure_gitignore(project)
    if args.url and args.content_file:
        fail("invalid_snapshot", "Use either --url or --content-file, not both")
    if not args.url and not args.content_file:
        fail("invalid_snapshot", "snapshot needs --url for E2 or --content-file for E1")
    file_name = unique_source_filename(directory, args.source_id)
    metadata: dict[str, Any] = {
        "sourceClass": args.source_class,
        "sourcePublishedAt": args.source_published_at,
        "filingDate": args.filing_date,
        "periodEnd": args.period_end,
        "observedMarketDate": args.observed_market_date,
        "query": args.query,
    }
    if args.url:
        try:
            text, fetch_meta = fetch_url(args.url)
        except Exception as exc:
            fail("url_not_admissible", f"E2 URL fetch refused or failed: {exc}")
        metadata.update(
            {
                "rung": "E2",
                "sourceLocator": args.url,
                "retrievalMethod": "gate-url-fetch",
                "verifiedSourceClasses": sorted(infer_source_classes_from_url(fetch_meta.get("finalUrl") or args.url, json_load(directory / "scope.json"))),
                **fetch_meta,
            }
        )
    else:
        content_path = Path(args.content_file).resolve()
        if not content_path.is_file():
            fail("invalid_snapshot", f"content file does not exist: {content_path}")
        text = content_path.read_text(encoding="utf-8", errors="replace")
        if not args.source_locator or not args.retrieval_method:
            fail("invalid_snapshot", "E1 snapshots require --source-locator and --retrieval-method")
        metadata.update(
            {
                "rung": "E1",
                "sourceLocator": args.source_locator,
                "retrievalMethod": args.retrieval_method,
            }
        )
    meta = write_source(directory, file_name, text, metadata)
    append_event(directory, {"action": "snapshot", "file": file_name, "rung": meta.get("rung"), "sourceLocator": meta.get("sourceLocator"), "contentHash": meta.get("contentHash")})
    print_json({"ok": True, "file": file_name, "rung": meta.get("rung"), "contentHash": meta.get("contentHash")})


def cmd_check(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    directory = run_dir(project, args.ticker)
    if not (directory / "scope.json").exists():
        fail("identity_unresolved", "Missing scope.json; run init first")
    report = run_check(directory)
    print_json(
        {
            "ok": report["ok"],
            "failures": report["failures"],
            "warnings": report["warnings"],
            "e1Disclosure": report.get("reportMeta", {}).get("e1Disclosure", []),
            "report": str(directory / "report.json"),
        }
    )
    if not report["ok"]:
        raise SystemExit(1)


def element_title(element_id: str) -> str:
    return RUBRIC_BY_ID[element_id]["label"]


def render_report_markdown(directory: Path, scope: dict[str, Any], research: dict[str, Any], report: dict[str, Any]) -> str:
    identity = scope.get("identity", {})
    lines = [
        f"# {identity_field_value(identity, 'legalName') or scope.get('legalName')} ({identity_field_value(identity, 'ticker') or scope.get('ticker')})",
        "",
        "## Cover",
        "",
        f"- Exchange: {identity_field_value(identity, 'exchange') or scope.get('exchange')}",
        f"- As-of: {scope.get('analysisAsOf') or report.get('generatedAt')}",
        f"- Citation snapshots: {len(load_sources(directory))}",
        "",
        "## Executive Summary",
        "",
    ]
    elements = research.get("elements", {}) if isinstance(research.get("elements"), dict) else {}
    bullets = []
    for element_id in ("business-model", "financial-analysis-3yr", "competitive-landscape", "risk-factors", "ai-relevance"):
        node = elements.get(element_id, {})
        summary = node.get("plainSummary") if isinstance(node, dict) else None
        if summary:
            bullets.append(f"- {summary}")
    lines.extend(bullets[:5] or ["- No executive summary bullets were finalized."])
    lines.extend(["", "## Deep Dive", ""])
    for element_id in RUBRIC_IDS:
        node = elements.get(element_id, {})
        lines.extend([f"### {element_title(element_id)}", ""])
        if isinstance(node, dict):
            lines.append(f"- Disposition: {node.get('disposition', 'unaccounted')}")
            if node.get("plainSummary"):
                lines.append(f"- Plain summary: {node['plainSummary']}")
            if node.get("reason"):
                lines.append(f"- Gap reasoning: {node['reason']}")
            if isinstance(node.get("subfacets"), dict):
                for subfacet, child in node["subfacets"].items():
                    if isinstance(child, dict):
                        lines.append(f"- {subfacet}: {child.get('disposition')}; {child.get('plainSummary', '').strip()}")
        else:
            lines.append("- Unaccounted.")
        lines.append("")
    lines.extend(["## Appendix", ""])
    lines.append("### Sourcing Strength")
    for item in report.get("reportMeta", {}).get("e1Disclosure", []):
        lines.append(f"- {item['claim']}: {item['note']}")
    if not report.get("reportMeta", {}).get("e1Disclosure"):
        lines.append("- No E1 citations were used.")
    lines.extend(["", "### Citation Ledger"])
    for citation in report.get("citationResults", []):
        if citation.get("verified"):
            lines.append(f"- {citation.get('element')} / {citation.get('claimId')}: {citation.get('file')} ({citation.get('effectiveRung')})")
    lines.extend(["", "### Methodology Note", ""])
    lines.append("The gate verifies saved evidence bytes, citations, rungs, dates, source classes, and grounding. It does not render a buy/sell/hold verdict or prove representative source selection.")
    return "\n".join(lines).rstrip() + "\n"


def cmd_finalize(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    directory = run_dir(project, args.ticker)
    if not (directory / "scope.json").exists():
        fail("identity_unresolved", "Missing scope.json; run init first")
    report = run_check(directory)
    if not report["ok"]:
        print_json({"ok": False, "failures": report["failures"], "message": "finalize refused because check failed"})
        raise SystemExit(1)
    scope = json_load(directory / "scope.json")
    research = json_load(directory / "research.json")
    report_md = render_report_markdown(directory, scope, research, report)
    (directory / "report.md").write_text(report_md, encoding="utf-8")
    append_event(directory, {"action": "finalize", "report": "report.md"})
    print_json({"ok": True, "report": str(directory / "report.md"), "reportJson": str(directory / "report.json"), "reportMeta": str(directory / "reportMeta.json")})


def cmd_status(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    directory = run_dir(project, args.ticker)
    payload = {
        "ok": True,
        "directory": str(directory),
        "hasScope": (directory / "scope.json").exists(),
        "hasResearch": (directory / "research.json").exists(),
        "hasReport": (directory / "report.json").exists(),
        "hasFinalReport": (directory / "report.md").exists(),
        "sources": sorted(load_sources(directory).keys()) if directory.exists() else [],
    }
    if (directory / "report.json").exists():
        report = json_load(directory / "report.json")
        payload["lastCheckOk"] = report.get("ok")
        payload["failureCount"] = len(report.get("failures", []))
        payload["warningCount"] = len(report.get("warnings", []))
    print_json(payload)


def cmd_probe_url(args: argparse.Namespace) -> None:
    require_posix()
    if args.ip:
        ok, detail = validate_ip_literal(args.ip)
        print_json({"ok": ok, "ip": args.ip, "detail": detail})
        if not ok:
            raise SystemExit(1)
        return
    if not args.url:
        fail("invalid_probe", "probe-url requires --url or --ip")
    parsed = urlsplit(args.url)
    try:
        if parsed.scheme not in {"https", "http"}:
            raise ValueError(f"scheme not allowed for E2: {parsed.scheme or '<missing>'}")
        if not parsed.hostname:
            raise ValueError("missing hostname")
        reject_reflector_url(args.url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        resolved, details = validate_resolved_host(parsed.hostname, port)
        classes = infer_source_classes_from_url(args.url)
        coverage = reflection_coverage(args.quote or "", args.url) if args.quote else 0.0
        quote_token_count = len(content_tokens(args.quote or ""))
        reflection_exempt = quote_token_count < REFLECTION_MIN_QUOTE_TOKENS
        ok = reflection_exempt or coverage < REFLECTION_THRESHOLD
        payload = {
            "ok": ok,
            "resolvedIps": resolved,
            "resolutionDetails": details,
            "verifiedSourceClasses": sorted(classes),
            "reflectionCoverage": coverage,
            "reflectionExempt": reflection_exempt,
        }
        print_json(payload)
        if not ok:
            raise SystemExit(1)
    except Exception as exc:
        print_json({"ok": False, "message": str(exc)})
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="techne diligence evidence gate")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="resolve and record company identity")
    init.add_argument("--project", type=Path, required=True)
    init.add_argument("--ticker", required=True)
    init.add_argument("--exchange", required=True)
    init.add_argument("--legal-name", required=True)
    init.add_argument("--identifier")
    init.add_argument("--identity-url", required=True)
    init.add_argument("--issuer-host", action="append")
    init.add_argument("--analysis-as-of")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    snapshot = sub.add_parser("snapshot", help="record one evidence snapshot")
    snapshot.add_argument("--project", type=Path, required=True)
    snapshot.add_argument("--ticker", required=True)
    snapshot.add_argument("--source-id", required=True)
    snapshot.add_argument("--source-class", required=True)
    source = snapshot.add_mutually_exclusive_group(required=True)
    source.add_argument("--url")
    source.add_argument("--content-file")
    snapshot.add_argument("--source-locator")
    snapshot.add_argument("--retrieval-method")
    snapshot.add_argument("--query")
    snapshot.add_argument("--source-published-at")
    snapshot.add_argument("--filing-date")
    snapshot.add_argument("--period-end")
    snapshot.add_argument("--observed-market-date")
    snapshot.set_defaults(func=cmd_snapshot)

    check = sub.add_parser("check", help="verify research.json")
    check.add_argument("--project", type=Path, required=True)
    check.add_argument("--ticker", required=True)
    check.set_defaults(func=cmd_check)

    finalize = sub.add_parser("finalize", help="render report.md after a clean check")
    finalize.add_argument("--project", type=Path, required=True)
    finalize.add_argument("--ticker", required=True)
    finalize.set_defaults(func=cmd_finalize)

    status = sub.add_parser("status", help="show current diligence artifacts")
    status.add_argument("--project", type=Path, required=True)
    status.add_argument("--ticker", required=True)
    status.set_defaults(func=cmd_status)

    probe = sub.add_parser("probe-url", help=argparse.SUPPRESS)
    probe.add_argument("--url")
    probe.add_argument("--ip")
    probe.add_argument("--quote")
    probe.set_defaults(func=cmd_probe_url)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

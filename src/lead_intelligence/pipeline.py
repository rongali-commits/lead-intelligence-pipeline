from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Lead:
    company: str
    industry: str
    location: str
    website: str
    email: str
    description: str
    source: str
    score: int = 0
    status: str = "review"


@dataclass(frozen=True)
class PipelineResult:
    collected: int
    unique: int
    duplicates_removed: int
    qualified: int
    minimum_score: int
    output_directory: Path


def run_pipeline(
    input_path: Path, output_directory: Path, minimum_score: int = 75
) -> PipelineResult:
    if not 0 <= minimum_score <= 100:
        raise ValueError("minimum_score must be between 0 and 100")
    output_directory.mkdir(parents=True, exist_ok=True)

    collected = _collect_local_html(input_path)
    unique = _deduplicate(collected)
    scored = [_score(lead, minimum_score) for lead in unique]
    qualified = [lead for lead in scored if lead.score >= minimum_score]

    _write_csv(output_directory / "all_leads.csv", scored)
    _write_csv(output_directory / "qualified_leads.csv", qualified)
    result = PipelineResult(
        collected=len(collected),
        unique=len(scored),
        duplicates_removed=len(collected) - len(scored),
        qualified=len(qualified),
        minimum_score=minimum_score,
        output_directory=output_directory,
    )
    (output_directory / "summary.json").write_text(
        json.dumps({**asdict(result), "output_directory": str(output_directory)}, indent=2),
        encoding="utf-8",
    )
    (output_directory / "dashboard.html").write_text(
        _dashboard_html(result, scored), encoding="utf-8"
    )
    return result


def _collect_local_html(input_path: Path) -> list[Lead]:
    soup = BeautifulSoup(input_path.read_text(encoding="utf-8"), "html.parser")
    leads: list[Lead] = []
    for card in soup.select("[data-company]"):
        website_node = card.select_one("a.website")
        email_node = card.select_one(".email")
        description_node = card.select_one(".description")
        leads.append(
            Lead(
                company=_clean(card.get("data-company", "")),
                industry=_clean(card.get("data-industry", "Unknown")) or "Unknown",
                location=_clean(card.get("data-location", "")),
                website=_normalize_url(website_node.get("href", "") if website_node else ""),
                email=_clean(email_node.get_text() if email_node else "").lower(),
                description=_clean(description_node.get_text() if description_node else ""),
                source=input_path.name,
            )
        )
    return leads


def _deduplicate(leads: list[Lead]) -> list[Lead]:
    records: dict[str, Lead] = {}
    for lead in leads:
        key = _lead_key(lead)
        current = records.get(key)
        if current is None or _completeness(lead) > _completeness(current):
            records[key] = lead
    return sorted(records.values(), key=lambda item: item.company.casefold())


def _lead_key(lead: Lead) -> str:
    domain = urlparse(lead.website).netloc.removeprefix("www.")
    if domain:
        return f"domain:{domain}"
    if EMAIL_PATTERN.match(lead.email):
        return f"email:{lead.email}"
    return f"company:{re.sub(r'[^a-z0-9]', '', lead.company.casefold())}"


def _completeness(lead: Lead) -> int:
    return sum(bool(value) for value in (lead.website, lead.email, lead.industry, lead.location, lead.description))


def _score(lead: Lead, minimum_score: int) -> Lead:
    score = 0
    score += 40 if lead.website else 0
    score += 25 if EMAIL_PATTERN.match(lead.email) else 0
    score += 15 if lead.industry and lead.industry != "Unknown" else 0
    score += 10 if lead.location else 0
    score += 10 if len(lead.description) >= 40 else 0
    if score >= 90:
        status = "qualified"
    elif score >= minimum_score:
        status = "review"
    else:
        status = "nurture"
    return replace(lead, score=score, status=status)


def _clean(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_url(value: str) -> str:
    value = _clean(value)
    if not value:
        return ""
    return value if value.startswith(("http://", "https://")) else f"https://{value}"


def _write_csv(path: Path, leads: list[Lead]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(Lead.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(lead) for lead in leads)


def _dashboard_html(result: PipelineResult, leads: list[Lead]) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(lead.company)}</td><td>{html.escape(lead.industry)}</td>"
        f"<td>{html.escape(lead.location)}</td><td><strong>{lead.score}</strong></td>"
        f"<td><span class='{lead.status}'>{lead.status}</span></td></tr>"
        for lead in sorted(leads, key=lambda item: -item.score)
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Lead intelligence report</title><style>
body{{margin:0;padding:44px;background:#071525;color:#eaf2ff;font:16px Inter,Arial,sans-serif}}main{{max-width:1120px;margin:auto}}.eyebrow{{color:#38bdf8;font-weight:800;letter-spacing:.12em;font-size:12px}}h1{{font-size:42px;margin:10px 0}}p{{color:#9fb0c6}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}}.stat,table{{background:#10243a;border:1px solid #203b57;border-radius:16px}}.stat{{padding:20px}}.stat strong{{display:block;font-size:31px}}table{{width:100%;border-collapse:collapse;overflow:hidden}}th,td{{padding:15px;text-align:left;border-bottom:1px solid #203b57}}th{{color:#7dd3fc;background:#0c1d30}}span.qualified,span.review,span.nurture{{padding:5px 10px;border-radius:999px;font-size:12px;font-weight:700}}span.qualified{{background:#14532d;color:#bbf7d0}}span.review{{background:#713f12;color:#fde68a}}span.nurture{{background:#334155;color:#cbd5e1}}@media(max-width:760px){{body{{padding:20px}}.stats{{grid-template-columns:1fr 1fr}}table{{font-size:13px}}}}
</style></head><body><main><div class="eyebrow">LOCAL SAMPLE / RESPONSIBLE COLLECTION</div><h1>Lead intelligence pipeline</h1><p>Normalized, deduplicated, scored, and exported from a fictional offline source.</p><section class="stats"><div class="stat"><strong>{result.collected}</strong>collected</div><div class="stat"><strong>{result.unique}</strong>unique</div><div class="stat"><strong>{result.duplicates_removed}</strong>duplicate removed</div><div class="stat"><strong>{result.qualified}</strong>score ≥ {result.minimum_score}</div></section><table><thead><tr><th>Company</th><th>Industry</th><th>Location</th><th>Score</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></main></body></html>"""


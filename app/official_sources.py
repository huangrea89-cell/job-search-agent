from __future__ import annotations

import json
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .models import SourceJob

USER_AGENT = "JobSearchAgent/0.1 (user-triggered; local single-user tool)"


def robots_allowed(url: str, robots_text: str) -> bool:
    parser = RobotFileParser()
    parser.set_url(urljoin(url, "/robots.txt"))
    parser.parse(robots_text.splitlines())
    return parser.can_fetch(USER_AGENT, url)


def parse_job_postings(html: str, page_url: str) -> list[SourceJob]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[SourceJob] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = payload.get("@graph", []) if isinstance(payload, dict) and "@graph" in payload else [payload]
        for item in candidates:
            if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                continue
            organization = item.get("hiringOrganization") or {}
            locations = item.get("jobLocation") or []
            if isinstance(locations, dict):
                locations = [locations]
            location_text = []
            for location in locations:
                address = location.get("address", {}) if isinstance(location, dict) else {}
                if isinstance(address, str):
                    location_text.append(address)
                else:
                    location_text.append(
                        " ".join(str(address[k]) for k in ("addressLocality", "addressRegion", "addressCountry") if address.get(k))
                    )
            employment = str(item.get("employmentType") or "unknown").lower()
            employment_type = "full_time" if "full" in employment or "全职" in employment else "unknown"
            source_url = str(item.get("url") or page_url)
            records.append(
                SourceJob(
                    source="official",
                    source_url=source_url,
                    official_url=source_url,
                    source_job_id=str(item.get("identifier", {}).get("value", "")) or None if isinstance(item.get("identifier"), dict) else None,
                    company=str(organization.get("name") or "未知公司"),
                    title=str(item.get("title") or "未知岗位"),
                    description=BeautifulSoup(str(item.get("description") or ""), "html.parser").get_text(" ", strip=True),
                    locations=[value for value in location_text if value],
                    employment_type=employment_type,
                    published_at=item.get("datePosted"),
                    metadata={"valid_through": item.get("validThrough"), "page_url": page_url},
                )
            )
    return records


def fetch_official_page(url: str, client: httpx.Client | None = None) -> list[SourceJob]:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise ValueError("official source URLs must use absolute HTTPS URLs")
    owns_client = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        robots = client.get(robots_url)
        if robots.status_code >= 400 or not robots_allowed(url, robots.text):
            raise PermissionError("robots policy does not explicitly allow this fetch")
        response = client.get(url)
        response.raise_for_status()
        return parse_job_postings(response.text, str(response.url))
    finally:
        if owns_client:
            client.close()

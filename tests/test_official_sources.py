import json

from app.official_sources import parse_job_postings, robots_allowed


def test_parse_public_json_ld_job_posting():
    posting = {
        "@context": "https://schema.org", "@type": "JobPosting", "title": "AI Product Manager",
        "description": "<p>Own user research</p>", "datePosted": "2026-09-01",
        "employmentType": "FULL_TIME", "url": "https://careers.example.com/jobs/1",
        "hiringOrganization": {"name": "Example Co"},
        "jobLocation": {"address": {"addressLocality": "上海", "addressCountry": "CN"}},
        "identifier": {"value": "1"},
    }
    html = f'<script type="application/ld+json">{json.dumps(posting)}</script>'
    records = parse_job_postings(html, "https://careers.example.com")
    assert len(records) == 1
    assert records[0].company == "Example Co"
    assert records[0].locations == ["上海 CN"]
    assert records[0].employment_type == "full_time"
    assert records[0].description == "Own user research"


def test_robots_rules_are_respected():
    assert robots_allowed("https://example.com/careers", "User-agent: *\nAllow: /careers")
    assert not robots_allowed("https://example.com/private/jobs", "User-agent: *\nDisallow: /private")

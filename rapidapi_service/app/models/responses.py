"""Pydantic response models — same shapes as pre-refactor main.py (Plan section 35/97)."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MetadataResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    metadata: Dict[str, Any]
    social_links: Dict[str, Optional[str]]
    contacts: Dict[str, List[str]]
    detected_technologies: List[str]
    technology_details: List[Dict[str, Any]] = []
    rss_feeds: List[str]
    json_ld_schemas: List[Any]
    security_score_percentage: float
    seo_score_percentage: float
    seo_passed_checks: List[str]
    seo_warnings: List[str]
    seo_checks: List[Dict[str, Any]] = []
    internal_links: List[str]
    external_links: List[str]
    total_internal_count: int
    total_external_count: int
    word_count: int
    reading_time_minutes: float
    markdown_content: str


class LinkPreviewResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    title: Optional[str]
    description: Optional[str]
    og_image: Optional[str]
    favicon: Optional[str]
    favicon_high_res: Optional[str] = None
    site_name: Optional[str]
    language: Optional[str]


class ContactsResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    emails: List[str]
    phones: List[str]
    social_links: Dict[str, Optional[str]]


class TechStackResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    detected_technologies: List[str]
    technology_details: List[Dict[str, Any]] = []


class SchemaResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    json_ld_count: int
    json_ld_schemas: List[Any]


class SecurityHeadersResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    security_score_percentage: float
    security_headers: Dict[str, Optional[str]]
    security_header_grades: Dict[str, str] = {}


class MarkdownResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    title: Optional[str]
    word_count: int
    reading_time_minutes: float
    summary_snippet: Optional[str] = None
    top_keywords: List[str] = []
    markdown_content: str


class SeoAuditResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    seo_score_percentage: float
    passed_checks: List[str]
    warnings: List[str]
    checks: List[Dict[str, Any]] = []


class LinksResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    total_links_count: int
    internal_links_count: int
    external_links_count: int
    internal_links: List[str]
    external_links: List[str]

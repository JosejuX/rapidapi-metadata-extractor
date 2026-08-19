"""
Pydantic response models — same shapes as pre-refactor main.py (Plan section
35/97).

Plan §35: sub-models for fields that were Dict[str, Any] blobs
(metadata/technology_details/seo_checks/phone_details) now have explicit,
documented fields instead. Each still sets `model_config = ConfigDict(extra
='allow')`: the extraction side (app/extraction/*.py) is the source of
truth for what these dicts actually contain, and a strict model would
silently DROP any field it doesn't know about (Pydantic's default is
extra='ignore') — which is exactly the bug this same pass found and fixed
for `product_data` (documented in this file's own sample response, but
missing from MetadataResponse, so /api/v1/extract silently never returned
it). `extra='allow'` gets the typing/OpenAPI-schema benefit for known
fields without that silent-data-loss risk for fields this file's authors
didn't think to list.

json_ld_schemas and product_data are deliberately left as loosely-typed
Dict[str, Any] / List[Any] — they mirror arbitrary Schema.org JSON-LD from
the target page (Plan §21.3: "no destruir el JSON-LD original"), which has
no fixed shape to model.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class SslStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool
    hsts_active: bool
    protocol: str


class HreflangTag(BaseModel):
    model_config = ConfigDict(extra="allow")

    lang: str
    url: str


class Metadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: Optional[str] = None
    description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: Optional[str] = None
    og_url: Optional[str] = None
    og_video: Optional[str] = None
    og_locale_alternate: List[str] = []
    keywords: Optional[str] = None
    author: Optional[str] = None
    site_name: Optional[str] = None
    language: Optional[str] = None
    favicon: Optional[str] = None
    favicon_high_res: Optional[str] = None
    canonical_url: Optional[str] = None
    theme_color: Optional[str] = None
    robots: Optional[str] = None
    hreflang_tags: List[HreflangTag] = []
    h1_tags: List[str] = []
    h1_count: int = 0
    images_count: int = 0
    images_missing_alt_count: int = 0
    links_count: int = 0
    video_embed_code: Optional[str] = None
    ssl_status: Optional[SslStatus] = None
    viewport: Optional[str] = None
    twitter_card: Optional[str] = None
    summary_snippet: Optional[str] = None
    top_keywords: List[str] = []
    content_length_bytes: Optional[int] = None


class TechnologyDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    confidence: float
    evidence: List[str] = []
    category: str


class SeoCheck(BaseModel):
    model_config = ConfigDict(extra="allow")

    check: str
    passed: bool
    severity: str
    evidence: str


class PhoneDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    raw: str
    normalized: Optional[str] = None
    country: Optional[str] = None
    possible: bool = False
    valid: bool = False


class ProductFieldConfidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: Optional[Any] = None
    confidence: float
    source: Optional[str] = None
    agreement: List[str] = []


class QualityWarning(BaseModel):
    model_config = ConfigDict(extra="allow")

    field: Optional[str] = None
    type: str


class Quality(BaseModel):
    model_config = ConfigDict(extra="allow")

    score: float
    rendered: bool = False
    sources_used: List[str] = []
    warnings: List[QualityWarning] = []


class ReadabilityMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    sentence_count: int
    paragraph_count: int
    avg_words_per_sentence: float
    heading_structure: Dict[str, int] = {}


class TlsCertificateDetails(BaseModel):
    model_config = ConfigDict(extra="allow")

    issuer: Optional[str] = None
    subject: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    tls_version: Optional[str] = None
    is_expired: bool = False


class MetadataResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    bot_protection_detected: bool = False
    redirect_count: int = 0
    is_shortened_url: bool = False
    metadata: Metadata
    readability: Optional[ReadabilityMetrics] = None
    social_links: Dict[str, Optional[str]]
    contacts: Dict[str, List[str]]
    phone_details: List[PhoneDetail] = []
    detected_technologies: List[str]
    technology_details: List[TechnologyDetail] = []
    rss_feeds: List[str]
    json_ld_schemas: List[Any]
    product_data: Optional[Dict[str, Any]] = None
    product_field_confidence: Dict[str, ProductFieldConfidence] = {}
    quality: Optional[Quality] = None
    security_score_percentage: float
    seo_score_percentage: float
    seo_passed_checks: List[str]
    seo_warnings: List[str]
    seo_checks: List[SeoCheck] = []
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
    bot_protection_detected: bool = False
    redirect_count: int = 0
    is_shortened_url: bool = False
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
    bot_protection_detected: bool = False
    redirect_count: int = 0
    is_shortened_url: bool = False
    emails: List[str]
    phones: List[str]
    phone_details: List[PhoneDetail] = []
    social_links: Dict[str, Optional[str]]


class TechStackResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    bot_protection_detected: bool = False
    redirect_count: int = 0
    is_shortened_url: bool = False
    detected_technologies: List[str]
    technology_details: List[TechnologyDetail] = []


class SchemaResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    bot_protection_detected: bool = False
    redirect_count: int = 0
    is_shortened_url: bool = False
    json_ld_count: int
    json_ld_schemas: List[Any]


class SecurityHeadersResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    bot_protection_detected: bool = False
    redirect_count: int = 0
    is_shortened_url: bool = False
    security_score_percentage: float
    security_headers: Dict[str, Optional[str]]
    security_header_grades: Dict[str, str] = {}
    tls_details: Optional[TlsCertificateDetails] = None


class MarkdownResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    bot_protection_detected: bool = False
    redirect_count: int = 0
    is_shortened_url: bool = False
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
    bot_protection_detected: bool = False
    redirect_count: int = 0
    is_shortened_url: bool = False
    seo_score_percentage: float
    passed_checks: List[str]
    warnings: List[str]
    checks: List[SeoCheck] = []
    readability: Optional[ReadabilityMetrics] = None


class LinksResponse(BaseModel):
    url: str
    final_url: str
    status_code: int
    execution_time_ms: float
    bot_protection_detected: bool = False
    redirect_count: int = 0
    is_shortened_url: bool = False
    total_links_count: int
    internal_links_count: int
    external_links_count: int
    internal_links: List[str]
    external_links: List[str]


# --------------------------------------------------------------------------
# Batch URL processing (competitive-differentiator #3): POST /api/v1/batch
# runs a lightweight PROFILE_LINK_PREVIEW extraction over up to
# MAX_BATCH_SIZE urls, one item at a time, one failure never taking down the
# rest of the batch — see app/api/batch.py.
# --------------------------------------------------------------------------
class BatchRequest(BaseModel):
    urls: List[str]


class BatchItemResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str
    success: bool
    error: Optional[str] = None
    final_url: Optional[str] = None
    status_code: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    og_image: Optional[str] = None
    favicon: Optional[str] = None
    site_name: Optional[str] = None
    language: Optional[str] = None
    redirect_count: int = 0
    is_shortened_url: bool = False


class BatchResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[BatchItemResult]


# --------------------------------------------------------------------------
# DNS / WHOIS domain intelligence (competitive-differentiator #5): GET
# /api/v1/domain — standalone lookups, no page fetch at all. See
# app/extraction/domain_intel.py and app/api/domain.py.
# --------------------------------------------------------------------------
class DnsRecords(BaseModel):
    model_config = ConfigDict(extra="allow")

    A: List[str] = []
    AAAA: List[str] = []
    MX: List[str] = []
    NS: List[str] = []
    TXT: List[str] = []


class WhoisInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    registrar: Optional[str] = None
    creation_date: Optional[str] = None
    expiration_date: Optional[str] = None
    name_servers: List[str] = []


class DomainInfoResponse(BaseModel):
    url: str
    hostname: str
    execution_time_ms: float
    dns_records: DnsRecords
    whois_info: Optional[WhoisInfo] = None

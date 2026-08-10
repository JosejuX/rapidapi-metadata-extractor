"""AI/LLM-ready Markdown reader endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.common import COMMON_RESPONSES
from app.extraction.pipeline import fetch_and_extract_raw
from app.extraction.profiles import PROFILE_MARKDOWN
from app.models.responses import MarkdownResponse
from app.ratelimit.limiter import check_ip_rate_limit
from app.security.headers import verify_rapidapi_secret

router = APIRouter(tags=["AI & LLM Reader"])


@router.get(
    "/api/v1/markdown",
    response_model=MarkdownResponse,
    responses=COMMON_RESPONSES,
    dependencies=[Depends(check_ip_rate_limit), Depends(verify_rapidapi_secret)],
)
async def extract_clean_markdown_article(
    url: str = Query(..., description="The target article/webpage URL to extract clean LLM-ready Markdown from"),
    user_agent: Optional[str] = Query(None, description="Optional custom User-Agent header")
):
    """
    Dedicated endpoint for AI Agents, ChatGPT, Claude & RAG pipelines:
    Strips noise (ads, navs, footers, scripts) and converts webpage article text into clean, structured Markdown with NLP auto-summary and keywords.
    """
    data = await fetch_and_extract_raw(url, user_agent, profile=PROFILE_MARKDOWN)
    meta = data["metadata"]
    return MarkdownResponse(
        url=data["url"],
        final_url=data["final_url"],
        status_code=data["status_code"],
        execution_time_ms=data["execution_time_ms"],
        title=meta["title"],
        word_count=data["word_count"],
        reading_time_minutes=data["reading_time_minutes"],
        summary_snippet=meta.get("summary_snippet"),
        top_keywords=meta.get("top_keywords", []),
        markdown_content=data["markdown_content"]
    )

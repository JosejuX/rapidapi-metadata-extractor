"""Embedded playground UI route."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.ui.templates import HOME_HTML

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
def home_ui():
    return HOME_HTML

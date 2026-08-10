"""HTTP security headers presence score (Plan section 24)."""
from typing import Any, Dict, Tuple


def extract_security_headers(resp_headers: Dict[str, str]) -> Tuple[Dict[str, Any], float]:
    sec_headers = {
        "strict_transport_security": resp_headers.get("strict-transport-security"),
        "content_security_policy": resp_headers.get("content-security-policy"),
        "x_frame_options": resp_headers.get("x-frame-options"),
        "x_content_type_options": resp_headers.get("x-content-type-options"),
        "referrer_policy": resp_headers.get("referrer-policy"),
        "permissions_policy": resp_headers.get("permissions-policy")
    }
    present_sec = sum(1 for v in sec_headers.values() if v is not None)
    security_score = round((present_sec / len(sec_headers)) * 100, 1)
    return sec_headers, security_score

"""Email extraction from visible text, merged with mailto: hrefs (Plan section 18)."""
import re
from typing import List

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

_IGNORED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js')
_IGNORED_DOMAINS = ('example.com', 'schema.org', 'w3.org', 'domain.com')


def extract_emails(clean_text: str, mailto_emails: List[str]) -> List[str]:
    emails = list(set(EMAIL_REGEX.findall(clean_text)))
    emails = [
        e for e in emails
        if not e.lower().endswith(_IGNORED_EXTENSIONS)
        and not any(domain in e.lower() for domain in _IGNORED_DOMAINS)
    ]

    for mail in mailto_emails:
        if mail not in emails:
            emails.append(mail)

    return emails

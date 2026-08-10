"""
Social link detection (Plan sections 17, 62): O(1) hostname dict lookup
instead of running 8+ regexes against every href.
"""
import re
from typing import Dict

# Social link detection: hostname -> platform_key.
# Plan §17: expanded to 20+ platforms, §62: dict-based for performance.
SOCIAL_HOSTNAME_MAP: Dict[str, str] = {
    # Twitter / X
    "twitter.com": "twitter", "www.twitter.com": "twitter",
    "x.com": "twitter",       "www.x.com": "twitter",
    # Facebook
    "facebook.com": "facebook", "www.facebook.com": "facebook",
    "fb.com": "facebook",
    # Instagram
    "instagram.com": "instagram", "www.instagram.com": "instagram",
    # LinkedIn
    "linkedin.com": "linkedin", "www.linkedin.com": "linkedin",
    # GitHub
    "github.com": "github", "www.github.com": "github",
    # YouTube
    "youtube.com": "youtube", "www.youtube.com": "youtube",
    "youtu.be": "youtube",
    # Telegram
    "t.me": "telegram", "telegram.me": "telegram",
    # TikTok
    "tiktok.com": "tiktok", "www.tiktok.com": "tiktok",
    # Threads
    "threads.net": "threads", "www.threads.net": "threads",
    # Bluesky
    "bsky.app": "bluesky",
    # Pinterest
    "pinterest.com": "pinterest", "www.pinterest.com": "pinterest",
    # Discord
    "discord.com": "discord", "discord.gg": "discord",
    # Reddit
    "reddit.com": "reddit", "www.reddit.com": "reddit",
    # Medium
    "medium.com": "medium", "www.medium.com": "medium",
    # GitLab
    "gitlab.com": "gitlab", "www.gitlab.com": "gitlab",
    # Dribbble
    "dribbble.com": "dribbble", "www.dribbble.com": "dribbble",
    # Behance
    "behance.net": "behance", "www.behance.net": "behance",
    # Vimeo
    "vimeo.com": "vimeo", "www.vimeo.com": "vimeo",
    # Snapchat
    "snapchat.com": "snapchat", "www.snapchat.com": "snapchat",
}
SOCIAL_PLATFORM_KEYS = set(SOCIAL_HOSTNAME_MAP.values())

# Legacy SOCIAL_DOMAINS kept for backward-compat patterns used in older tests only.
SOCIAL_DOMAINS = {
    'twitter': re.compile(r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+', re.I),
    'facebook': re.compile(r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+', re.I),
    'instagram': re.compile(r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+', re.I),
    'linkedin': re.compile(r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9._-]+', re.I),
    'github': re.compile(r'https?://(?:www\.)?github\.com/[a-zA-Z0-9._-]+', re.I),
    'youtube': re.compile(r'https?://(?:www\.)?youtube\.com/(?:c/|channel/|@)?[a-zA-Z0-9._-]+', re.I),
    'telegram': re.compile(r'https?://(?:t\.me|telegram\.me)/[a-zA-Z0-9._-]+', re.I),
    'tiktok': re.compile(r'https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9._-]+', re.I)
}

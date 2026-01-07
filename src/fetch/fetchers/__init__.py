"""
Fetcher implementations
"""

# Import fetchers to trigger registration
from . import standard_rss  # noqa: F401
from . import sixtys_digest  # noqa: F401
from . import ai_daily_news  # noqa: F401
from . import today_in_history  # noqa: F401

__all__ = []

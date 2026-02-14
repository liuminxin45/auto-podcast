import pytest


pytestmark = pytest.mark.skip(
    reason="Discovery-layer focus prefilter/query-aware source fetch was removed; fetch now collects data completely before downstream filtering."
)

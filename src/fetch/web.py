from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup


def extract_main_text(url: str, timeout_seconds: int) -> str:
    log = logging.getLogger("fetch.web")

    resp = requests.get(
        url,
        timeout=timeout_seconds,
        headers={"User-Agent": "podcast-bot/0.1"},
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n".join([ln for ln in lines if ln])

    if len(cleaned) < 200:
        log.info("extracted text too short: %s", url)

    return cleaned

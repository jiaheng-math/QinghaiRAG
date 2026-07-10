from __future__ import annotations

import hashlib
import re

from bs4 import BeautifulSoup

BLOCK_TAGS = ("article", "main", "section", "div", "p", "table", "h1", "h2", "h3")


def normalize_punctuation(text: str) -> str:
    translations = str.maketrans({",": "，", ";": "；", ":": "：", "?": "？", "!": "！"})
    return text.translate(translations)


def deduplicate_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        key = re.sub(r"\s+", "", line)
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def clean_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    root = (
        soup.select_one(".app-content-body")
        or soup.find("article")
        or soup.find("main")
        or soup.body
        or soup
    )
    lines = []
    for element in root.find_all(BLOCK_TAGS):
        if element.find_parent(BLOCK_TAGS) and element.name in {"div", "section"}:
            continue
        value = re.sub(r"[ \t\u3000]+", " ", element.get_text(" ", strip=True))
        value = re.sub(r"\s*\n\s*", "\n", value).strip()
        if value:
            lines.append(value)
    if not lines:
        lines = [root.get_text("\n", strip=True)]
    text = "\n".join(deduplicate_lines(lines))
    text = normalize_punctuation(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return title, text


def make_doc_id(source_id: str, text: str) -> str:
    digest = hashlib.sha256(f"{source_id}\0{text}".encode()).hexdigest()[:12]
    return f"doc_{digest}"

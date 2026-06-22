"""Small RSS/Atom parsing helpers used by crawler spiders."""

from __future__ import annotations

from xml.etree import ElementTree


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _children(element, name: str):
    return [child for child in list(element) if _local_name(child.tag) == name]


def _child_text(element, name: str) -> str:
    for child in _children(element, name):
        if child.text:
            return child.text.strip()
    return ""


def _rss_entry(item) -> dict:
    categories = [
        category.text.strip()
        for category in _children(item, "category")
        if category.text and category.text.strip()
    ]
    description = _child_text(item, "description") or _child_text(item, "summary")
    return {
        "title": _child_text(item, "title"),
        "link": _child_text(item, "link"),
        "content": description,
        "summary": _child_text(item, "summary") or description,
        "published_at": _child_text(item, "pubDate") or _child_text(item, "published"),
        "authors": [],
        "tags": categories,
    }


def _atom_link(entry) -> str:
    fallback = ""
    for link in _children(entry, "link"):
        href = (link.attrib.get("href") or "").strip()
        if not href:
            continue
        if (link.attrib.get("rel") or "alternate") == "alternate":
            return href
        fallback = fallback or href
    return fallback


def _atom_entry(entry) -> dict:
    authors = []
    for author in _children(entry, "author"):
        name = _child_text(author, "name")
        if name:
            authors.append(name)
    tags = [
        category.attrib.get("term", "").strip()
        for category in _children(entry, "category")
        if category.attrib.get("term", "").strip()
    ]
    content = _child_text(entry, "content") or _child_text(entry, "summary")
    return {
        "title": _child_text(entry, "title"),
        "link": _atom_link(entry),
        "content": content,
        "summary": _child_text(entry, "summary") or content,
        "published_at": _child_text(entry, "published") or _child_text(entry, "updated"),
        "authors": authors,
        "tags": tags,
    }


def extract_feed_entries(xml_text: str) -> list[dict]:
    """Extract normalized entries from RSS 2.0 or Atom XML."""
    if not xml_text.strip():
        return []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []

    entries = []
    for element in root.iter():
        local = _local_name(element.tag)
        if local == "item":
            entries.append(_rss_entry(element))
        elif local == "entry":
            entries.append(_atom_entry(element))
    return [entry for entry in entries if entry["title"] and entry["link"]]

#!/usr/bin/env python3
"""Migrate drafts from ~/workspace/company/affiliate-site/content/drafts/ to _posts/.

Rules:
- Dedup by (slug, lang): keep the latest-dated version
- EN: _posts/YYYY-MM-DD-<slug>.md, permalink /posts/<slug>/
- JA: _posts/YYYY-MM-DD-<slug>-ja.md, permalink /posts/<slug>-ja/
- Strip <!-- samtinker-brand-v1 --> marker
- Generate frontmatter (title, description, date, categories, tags, lang)
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

DRAFTS = Path.home() / "workspace/company/affiliate-site/content/drafts"
POSTS = Path(__file__).resolve().parent.parent / "_posts"

FNAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+?)(_ja)?\.md$")

CATEGORY_RULES = [
    (("runway", "kling", "sora", "pika", "video-generator", "animation", "video"),
     ["AI Tools", "Video Generation"]),
    (("elevenlabs", "murf", "voice", "clone-voice", "podcast"),
     ["AI Tools", "Voice AI"]),
    (("heygen", "synthesia", "avatar"),
     ["AI Tools", "Avatar"]),
    (("elearning",), ["AI Tools", "Education"]),
    (("real-estate",), ["AI Tools", "Real Estate"]),
    (("fliki", "invideo"), ["AI Tools", "Video Production"]),
]


def infer_categories(slug: str) -> list[str]:
    s = slug.lower()
    for keywords, cats in CATEGORY_RULES:
        if any(k in s for k in keywords):
            return cats
    return ["AI Tools"]


def extract_tags(slug: str) -> list[str]:
    parts = [p for p in slug.replace("_", "-").split("-") if len(p) >= 3]
    filler = {"for", "the", "with", "vs", "free", "from", "your", "and"}
    return [p for p in parts if p not in filler][:6]


def extract_title_and_description(content: str) -> tuple[str, str]:
    lines = content.splitlines()
    title = ""
    for line in lines:
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            title = m.group(1)
            break

    description = ""
    # Find first substantive paragraph (skip Last updated/author block/affiliate line)
    in_blockquote = False
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        if s.startswith("*Last updated") or s.startswith("*Disclosure"):
            continue
        if s.startswith(">"):
            in_blockquote = True
            continue
        if in_blockquote and (s.startswith(">") or s.startswith("*") or s.startswith("[")):
            continue
        in_blockquote = False
        # first real paragraph
        description = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
        description = re.sub(r"\*+", "", description)
        break
    if len(description) > 200:
        description = description[:197].rstrip() + "..."
    return title, description


def build_frontmatter(*, title: str, description: str, date: str, slug: str, lang: str, pin: bool) -> str:
    cats = infer_categories(slug)
    tags = extract_tags(slug)
    date_iso = f"{date} 09:00:00 +0900"
    permalink = f"/posts/{slug}{'-ja' if lang == 'ja' else ''}/"
    parts = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f'description: "{description.replace(chr(34), chr(39))}"',
        f"date: {date_iso}",
        f"categories: [{', '.join(cats)}]",
        f"tags: [{', '.join(tags)}]",
        f"permalink: {permalink}",
    ]
    if lang == "ja":
        parts.append("lang: ja")
    if pin:
        parts.append("pin: true")
    parts.append("---\n")
    return "\n".join(parts)


def strip_title_and_marker(content: str) -> str:
    # Remove first H1
    out = re.sub(r"^#\s+.+?\n\n?", "", content, count=1, flags=re.MULTILINE)
    # Remove samtinker-brand marker
    out = re.sub(r"<!--\s*samtinker-brand-v1\s*-->\s*", "", out)
    return out.rstrip() + "\n"


def main() -> None:
    entries: dict[tuple[str, str], tuple[str, Path]] = {}
    for f in sorted(DRAFTS.glob("*.md")):
        m = FNAME_RE.match(f.name)
        if not m:
            print(f"SKIP (bad filename): {f.name}")
            continue
        date, slug, ja = m.groups()
        lang = "ja" if ja else "en"
        key = (slug, lang)
        # Keep latest
        if key not in entries or entries[key][0] < date:
            entries[key] = (date, f)

    print(f"Dedup → {len(entries)} unique (slug, lang) pairs")

    # Wipe existing _posts except placeholder and the bootstrap runway-vs-kling
    for p in POSTS.glob("*.md"):
        p.unlink()

    for (slug, lang), (date, src) in sorted(entries.items()):
        raw = src.read_text(encoding="utf-8")
        title, description = extract_title_and_description(raw)
        if not title:
            print(f"SKIP (no title): {src.name}")
            continue
        body = strip_title_and_marker(raw)
        fm = build_frontmatter(
            title=title,
            description=description or title,
            date=date,
            slug=slug,
            lang=lang,
            pin=(lang == "en" and slug == "runway-vs-kling"),
        )
        out_name = f"{date}-{slug}{'-ja' if lang == 'ja' else ''}.md"
        out = POSTS / out_name
        out.write_text(fm + "\n" + body, encoding="utf-8")
        print(f"  {out_name} ← {src.name}")


if __name__ == "__main__":
    main()

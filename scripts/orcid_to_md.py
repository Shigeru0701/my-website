#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORCID の Works を取得して publications.md を生成（年ごと見出し・書誌整形）
- ORCID_ID：環境変数（例: 0000-0001-9008-2123）
- 出力先：リポジトリ直下の publications.md
- 体裁：年降順。タイトル太字・ジャーナル斜体。DOI/PMID/PMCID リンク
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

# ===== 設定 =====
ORCID_ID = os.environ.get("ORCID_ID", "").strip()
if not ORCID_ID:
    sys.exit("ERROR: ORCID_ID is not set.")
BASE = f"https://pub.orcid.org/v3.0/{ORCID_ID}"

# 自分の氏名（太字化に使用）
MY_FAMILY_NAME = "Fujita"
MY_GIVEN_NAMES = "Shigeru"


# ===== ORCID 取得ユーティリティ =====
def fetch_json(url: str):
    """ORCID Public API から JSON を取得（CI 安定化のため User-Agent を付与）"""
    headers = {
        "Accept": "application/json",
        "User-Agent": "GitHubActions/ORCID-Fetcher (+https://github.com/)"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:500]
        print(f"[HTTPError] {e.code} {e.reason} at {url}\n{body}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"[URLError] {e.reason} at {url}", file=sys.stderr)
        raise


def get_putcodes():
    """Works の put-code 一覧を取得"""
    data = fetch_json(f"{BASE}/works")
    pcs = []
    for g in data.get("group", []):
        for ws in g.get("work-summary", []):
            pc = ws.get("put-code")
            if pc is not None:
                pcs.append(pc)
    return sorted(set(pcs))


def parse_year(d: dict) -> int:
    y = (d.get("publication-date") or {}).get("year", {}).get("value")
    try:
        return int(y)
    except Exception:
        return -1  # 不明


def extract_ids(d: dict):
    """DOI/PMID/PMCID を抽出"""
    doi = pmid = pmcid = None
    for e in (d.get("external-ids", {}) or {}).get("external-id", []):
        t = (e.get("external-id-type") or "").lower()
        v = (e.get("external-id-value") or "").strip()
        if t == "doi":
            doi = v
        elif t == "pmid":
            pmid = v
        elif t == "pmcid":
            pmcid = v
    return doi, pmid, pmcid


def fmt_authors(contributors: dict) -> str:
    """著者表記（自分は太字）"""
    if not contributors:
        return ""
    names = []
    for c in contributors.get("contributor", []):
        credit = (c.get("credit-name") or {}).get("value")
        if credit:
            name = credit
        else:
            gn = (((c.get("contributor-orcid") or {}).get("person") or {})
                  .get("name") or {}).get("given-names", {}).get("value") or ""
            fn = (((c.get("contributor-orcid") or {}).get("person") or {})
                  .get("name") or {}).get("family-name", {}).get("value") or ""
            if not (gn or fn):
                gn = (c.get("contributor-attributes") or {}).get("contributor-given-name", {}).get("value") or ""
                fn = (c.get("contributor-attributes") or {}).get("contributor-family-name", {}).get("value") or ""
            name = " ".join([gn, fn]).strip()

        low = name.lower()
        if MY_FAMILY_NAME.lower() in low and MY_GIVEN_NAMES.lower() in low:
            name = f"**{name}**"
        names.append(name)

    names = [n for n in names if n]
    return ", ".join(names)


def entry(putcode: int):
    """1件分（年, Markdown行）"""
    d = fetch_json(f"{BASE}/work/{putcode}")
    title = (d.get("title", {}) or {}).get("title", {}).get("value") or "Untitled"
    journal = (d.get("journal-title") or {}).get("value") or ""
    year = parse_year(d)
    authors = fmt_authors(d.get("contributors"))

    doi, pmid, pmcid = extract_ids(d)
    links = []
    if doi:
        links.append(f'<a href="https://doi.org/{doi}">DOI</a>')
    if pmid:
        links.append(f'<a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/">PMID</a>')
    if pmcid:
        links.append(f'<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/">PMCID</a>')

    j = f"*{journal}*" if journal else ""

    # 先頭 "- " は後で外して span 付与に使う
    line = "- "
    if authors:
        line += f"{authors}. "
    line += f"**{title}.** {j} {year if year > 0 else ''} "
    if links:
        line += '<span class="links">' + " | ".join(links) + "</span>"
    return year, line.strip()


# ===== 年見出し付きで Markdown を組み立てる =====
def build_markdown(entries):
    """
    entries: [(year, line), ...]   年降順に整列済みを想定
    """
    lines = [
        "---",
        "title: Publications",
        "---",
        "",
        '<link rel="stylesheet" href="./assets/style.css">',
        "<h1>Publications</h1>",
        "",
        "> *This list syncs from ORCID. Entries are shown in **reverse chronological** order.*",
        '<hr class="soft" />',
        ""
    ]

    cur_year = None
    open_ul = False

    for y, ln in entries:
        if y != cur_year:
            if open_ul:
                lines.append("</ul>")
                open_ul = False
            cur_year = y
            if cur_year and cur_year > 0:
                lines.append(f'<div class="year-block">{cur_year}</div>')
            else:
                lines.append('<div class="year-block">Unknown year</div>')
            lines.append('<ul class="publist">')
            open_ul = True

        # "- " を外してタイトル/ジャーナルを span に
        txt = ln[2:].strip()
        if "**" in txt:
            txt = txt.replace("**", '<span class="title">', 1)
            txt = txt.replace("**", "</span>", 1)
        if "*" in txt:
            txt = txt.replace("*", '<span class="journal">', 1)
            txt = txt.replace("*", "</span>", 1)

        lines.append(f"<li>{txt}</li>")

    if open_ul:
        lines.append("</ul>")

    lines.append("")
    lines.append(f"_Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC_")
    return "\n".join(lines)


# ===== メイン =====
def main():
    putcodes = get_putcodes()
    items = []
    for pc in putcodes:
        try:
            items.append(entry(pc))
        except Exception as e:
            print(f"[WARN] put-code {pc}: {e}", file=sys.stderr)

    # 年降順
    items.sort(key=lambda x: x[0], reverse=True)
    md = build_markdown(items)

    with open("publications.md", "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Generated publications.md ({len(items)} entries).")


if __name__ == "__main__":
    main()
``

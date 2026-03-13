#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORCID Public API から Works を取得し、GitHub Pages 用の publications.md を生成する。
- ORCID_ID は環境変数 ORCID_ID から受け取る（例: 0000-0001-9008-2123）
- 生成先: ./publications.md
- 形式: 年降順。DOI/PMID による外部リンク。筆頭著者がユーザーの場合は太字。
参考:
- ORCID Public API: https://pub.orcid.org/v3.0/
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

ORCID_ID = os.environ.get("ORCID_ID", "").strip()
MY_FAMILY_NAME = "Fujita"
MY_GIVEN_NAMES = "Shigeru"

if not ORCID_ID:
    sys.exit("ERROR: ORCID_ID is not set.")

BASE = f"https://pub.orcid.org/v3.0/{ORCID_ID}"

def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_putcodes():
    data = fetch_json(f"{BASE}/works")
    # works.group[].work-summary[].put-code
    putcodes = []
    for g in data.get("group", []):
        for ws in g.get("work-summary", []):
            pc = ws.get("put-code")
            if pc is not None:
                putcodes.append(pc)
    return sorted(set(putcodes))

def get_citation_identifiers(work_detail: dict):
    """ DOI/PMID/PMCID を拾う """
    doi = pmid = pmcid = None
    ext_ids = work_detail.get("external-ids", {}).get("external-id", [])
    for e in ext_ids:
        id_type = (e.get("external-id-type") or "").lower()
        val = e.get("external-id-value") or ""
        if id_type == "doi":
            doi = val
        elif id_type == "pmid":
            pmid = val
        elif id_type == "pmcid":
            pmcid = val
    return doi, pmid, pmcid

def fmt_authors(contributors):
    """ 著者名列挙。自分は太字。 """
    names = []
    if not contributors:
        return ""
    for c in contributors.get("contributor", []):
        cr = c.get("credit-name", {}).get("value")
        given = c.get("contributor-attributes", {}).get("contributor-given-name", {}).get("value")
        family = c.get("contributor-attributes", {}).get("contributor-family-name", {}).get("value")
        # credit-name があればそれを優先
        if cr:
            name = cr
        else:
            given_name = c.get("contributor-orcid", {}).get("person", {}).get("name", {}).get("given-names", {}).get("value") \
                        or given or ""
            family_name = c.get("contributor-orcid", {}).get("person", {}).get("name", {}).get("family-name", {}).get("value") \
                         or family or ""
            name = " ".join([given_name, family_name]).strip()
        # 自分の名前を太字に
        if (MY_FAMILY_NAME.lower() in name.lower()) and (MY_GIVEN_NAMES.lower() in name.lower()):
            name = f"**{name}**"
        names.append(name)
    return ", ".join([n for n in names if n])

def year_from_detail(d):
    y = (
        d.get("publication-date", {}) or {}
    ).get("year", {}).get("value")
    try:
        return int(y)
    except Exception:
        return -1

def entry_from_putcode(pc):
    d = fetch_json(f"{BASE}/work/{pc}")
    title = d.get("title", {}).get("title", {}).get("value") or "Untitled"
    journal = d.get("journal-title", {}).get("value") or ""
    year = year_from_detail(d)
    contributors = d.get("contributors")
    authors_str = fmt_authors(contributors)
    doi, pmid, pmcid = get_citation_identifiers(d)

    links = []
    if doi:
        links.append(f"DOI: https://doi.org/{doi}")
    if pmid:
        links.append(f"PMID: https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
    if pmcid:
        links.append(f"PMCID: https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/")

    # 雑誌名が空なら外す
    j = f"*{journal}*" if journal else ""
    # 形式: Authors. **Title.** _Journal_ Year. links
    line = "- "
    if authors_str:
        line += f"{authors_str}. "
    line += f"**{title}.** "
    if j:
        line += f"{j} "
    if year > 0:
        line += f"{year}. "
    if links:
        line += " " + " | ".join(links)
    return year, line.strip()

def build_markdown(entries):
    lines = [
        "---",
        "title: Publications",
        "---",
        "",
        "./assets/style.css",
        "<h1>Publications</h1>",
        "",
        "> 自動生成（ORCID 連携）。**太字** はあなたの氏名です。",
        ""
    ]
    # 年降順
    entries.sort(key=lambda x: x[0], reverse=True)
    for _, ln in entries:
        lines.append(ln)
    lines.append("")
    lines.append(f"_Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC_")
    return "\n".join(lines)

def main():
    pcs = get_putcodes()
    entries = []
    for pc in pcs:
        try:
            entries.append(entry_from_putcode(pc))
        except Exception as e:
            print(f"WARN: failed to parse put-code={pc}: {e}", file=sys.stderr)
    md = build_markdown(entries)
    with open("publications.md", "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Generated publications.md with {len(entries)} entries.")

if __name__ == "__main__":
    main()
``

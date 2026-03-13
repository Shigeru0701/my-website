#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, sys, urllib.request, urllib.error
from datetime import datetime

ORCID_ID = os.environ.get("ORCID_ID", "").strip()
if not ORCID_ID:
    sys.exit("ERROR: ORCID_ID is not set.")
BASE = f"https://pub.orcid.org/v3.0/{ORCID_ID}"

def fetch_json(url):
    headers = {
        "Accept": "application/json",
        "User-Agent": "GitHubActions/ORCID-Fetcher (+https://github.com/)"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def get_putcodes():
    data = fetch_json(f"{BASE}/works")
    pcs = []
    for g in data.get("group", []):
        for ws in g.get("work-summary", []):
            pc = ws.get("put-code")
            if pc is not None:
                pcs.append(pc)
    return sorted(set(pcs))

def entry(pc):
    d = fetch_json(f"{BASE}/work/{pc}")
    title = d.get("title", {}).get("title", {}).get("value") or "Untitled"
    journal = d.get("journal-title", {}).get("value") or ""
    year = d.get("publication-date", {}).get("year", {}).get("value")
    try: year = int(year)
    except: year = -1
    # 簡易リンク（DOI/PMID）
    doi = pmid = None
    for e in d.get("external-ids", {}).get("external-id", []):
        t = (e.get("external-id-type") or "").lower()
        v = e.get("external-id-value") or ""
        if t == "doi": doi = v
        if t == "pmid": pmid = v
    links = []
    if doi: links.append(f"DOI: https://doi.org/{doi}")
    if pmid: links.append(f"PMID: https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
    j = f"*{journal}*" if journal else ""
    line = f"- **{title}.** {j} {year if year>0 else ''} " + (" | ".join(links))
    return year, line.strip()

def main():
    pcs = get_putcodes()
    items = []
    for pc in pcs:
        try: items.append(entry(pc))
        except Exception as e:
            print(f"[WARN] put-code {pc}: {e}", file=sys.stderr)
    items.sort(key=lambda x: x[0], reverse=True)
    out = ["---","title: Publications","---","","./assets/style.css","<h1>Publications</h1>",""]
    out += [ln for _, ln in items]
    out += ["", f"_Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC_"]
    with open("publications.md","w",encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"Generated publications.md ({len(items)} entries).")

if __name__ == "__main__":
    main()

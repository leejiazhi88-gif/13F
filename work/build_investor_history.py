#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path

from build_berkshire_data import (
    ROOT,
    USER_AGENT,
    build_changes,
    clean_number,
    normalize_values,
    parse_html_table,
    parse_structured_xml,
    period_from_date,
)


START_DATE = "2016-06-30"
DATA_DIR = ROOT / "investor_13f_data"
MANAGERS = {
    "himalaya": {"cik": "1709323", "name": "Himalaya Capital Management"},
    "pershing": {"cik": "1336528", "name": "Pershing Square"},
    "tci": {"cik": "1647251", "name": "TCI Fund Management"},
    "baupost": {"cik": "1061768", "name": "Baupost Group"},
    "duquesne": {"cik": "1536411", "name": "Duquesne Family Office"},
    "appaloosa": {"cik": "1656456", "name": "Appaloosa LP"},
    "third-point": {"cik": "1040273", "name": "Third Point LLC"},
    "trian": {"cik": "1345471", "name": "Trian Fund Management"},
    "icahn": {"cik": "921669", "name": "Carl C. Icahn"},
    "scion": {"cik": "1649339", "name": "Scion Asset Management"},
    "coatue": {"cik": "1135730", "name": "Coatue Management"},
    "tiger-global": {"cik": "1167483", "name": "Tiger Global Management"},
    "viking": {"cik": "1103804", "name": "Viking Global Investors"},
    "lone-pine": {"cik": "1061165", "name": "Lone Pine Capital"},
    "altimeter": {"cik": "1541617", "name": "Altimeter Capital Management"},
    "hhlr": {"cik": "1762304", "name": "HHLR Advisors"},
    "aspex": {"cik": "1768375", "name": "Aspex Management (HK)"},
    "renaissance": {"cik": "1037389", "name": "Renaissance Technologies"},
    "de-shaw": {"cik": "1009207", "name": "D. E. Shaw & Co."},
}


def fetch_json(url):
    return json.loads(fetch_bytes(url).decode("utf-8"))


def fetch_bytes(url):
    result = subprocess.run(
        ["curl", "-L", "-A", USER_AGENT, "--retry", "2", "--retry-delay", "1", url],
        check=True,
        capture_output=True,
    )
    return result.stdout


def submissions_for(cik):
    padded = cik.zfill(10)
    path = DATA_DIR / f"CIK{padded}.json"
    data = fetch_json(f"https://data.sec.gov/submissions/CIK{padded}.json")
    path.write_text(json.dumps(data, indent=2))
    return data


def load_13f_filings(cik):
    data = submissions_for(cik)
    recent = data["filings"]["recent"]
    rows = []
    seen_dates = set()
    for idx, form in enumerate(recent["form"]):
        report_date = recent["reportDate"][idx]
        if form != "13F-HR" or report_date < START_DATE:
            continue
        if report_date in seen_dates:
            continue
        seen_dates.add(report_date)
        accession = recent["accessionNumber"][idx]
        rows.append({
            "reportDate": report_date,
            "filingDate": recent["filingDate"][idx],
            "accession": accession,
            "accessionCompact": accession.replace("-", ""),
        })
    return sorted(rows, key=lambda item: item["reportDate"])


def find_info_table_name(index):
    names = [item["name"] for item in index["directory"]["item"]]
    for name in names:
        lower = name.lower()
        if lower == "form13finfotable.xml" or lower == "infotable.xml":
            return name
    for name in names:
        lower = name.lower()
        if "infotable" in lower and lower.endswith((".xml", ".html", ".htm")):
            return name
    for name in names:
        lower = name.lower()
        if lower.endswith(".xml") and "primary" not in lower and "doc" not in lower:
            return name
    return None


def download_info_table(manager_key, cik, filing):
    manager_dir = DATA_DIR / manager_key
    manager_dir.mkdir(parents=True, exist_ok=True)
    accession = filing["accessionCompact"]
    table_path = manager_dir / f"{filing['reportDate']}_{accession}_13f.xml"
    if table_path.exists():
        return table_path
    index_path = manager_dir / f"{filing['reportDate']}_{accession}_index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())
    else:
        index = fetch_json(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/index.json")
        index_path.write_text(json.dumps(index, indent=2))
    table_name = find_info_table_name(index)
    if not table_name:
        raise RuntimeError(f"No info table: {manager_key} {filing['reportDate']} {filing['accession']}")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{table_name}"
    table_path.write_bytes(fetch_bytes(url))
    return table_path


def parse_table(path, report_date):
    text = path.read_text(errors="ignore")
    if re.search(r"<(?:[\w.-]+:)?infoTable\b", text, re.I):
        return parse_structured_xml(text)
    return parse_html_table(text)


def ticker_guess(row):
    issuer = row["issuer"]
    compact = re.sub(r"[^A-Z0-9]+", " ", issuer).strip()
    return compact[:24] if compact else row["cusip"]


def summarize_snapshot(snapshot):
    total = snapshot["totalValue"]
    holdings = snapshot["holdings"]
    top = [
        [ticker_guess(row), row["issuer"], (row["value"] / total) * 100 if total else 0]
        for row in holdings[:5]
    ]
    top10 = sum(row["value"] for row in holdings[:10]) / total * 100 if total else 0
    return {
        "value": total,
        "holdings": len(holdings),
        "filed": snapshot["filingDate"],
        "top10": top10,
        "top": top,
        "signal": f"{snapshot['period']} 前五大为 " + "、".join(row[0] for row in top[:3]) + " 等。",
    }


def aggregate_by_issuer(holdings):
    grouped = {}
    for row in holdings:
        issuer = row["issuer"]
        if issuer not in grouped:
            grouped[issuer] = {
                "issuer": issuer,
                "value": 0,
                "shares": 0,
            }
        grouped[issuer]["value"] += row["value"]
        grouped[issuer]["shares"] += row["shares"]
    return sorted(grouped.values(), key=lambda row: row["value"], reverse=True)


def build_core_trend(snapshots, limit=6):
    if not snapshots:
        return {"periods": [], "series": []}
    latest = snapshots[-1]
    latest_total = latest["totalValue"]
    core_names = [
        row["issuer"]
        for row in aggregate_by_issuer(latest["holdings"])[:limit]
        if row["value"] > 0
    ]
    periods = [
        {
            "period": snapshot["period"],
            "reportDate": snapshot["reportDate"],
            "filingDate": snapshot["filingDate"],
            "totalValue": snapshot["totalValue"],
        }
        for snapshot in snapshots
    ]
    series = []
    for issuer in core_names:
        points = []
        for snapshot in snapshots:
            total = snapshot["totalValue"]
            value = sum(row["value"] for row in snapshot["holdings"] if row["issuer"] == issuer)
            points.append({
                "period": snapshot["period"],
                "reportDate": snapshot["reportDate"],
                "value": value,
                "weight": value / total if total else 0,
            })
        series.append({
            "name": issuer,
            "weight": sum(row["value"] for row in latest["holdings"] if row["issuer"] == issuer) / latest_total if latest_total else 0,
            "points": points,
        })
    return {"periods": periods, "series": series}


def build_manager_history(manager_key, meta):
    filings = load_13f_filings(meta["cik"])
    history = {}
    snapshots = []
    previous = None
    for filing in filings:
        try:
            path = download_info_table(manager_key, meta["cik"], filing)
        except RuntimeError as exc:
            if not str(exc).startswith("No info table:"):
                raise
            print(f"warning: {exc}; skipping quarter and resetting change baseline", file=sys.stderr)
            previous = None
            continue
        holdings = parse_table(path, filing["reportDate"])
        snapshot = {
            "period": period_from_date(filing["reportDate"]),
            "reportDate": filing["reportDate"],
            "filingDate": filing["filingDate"],
            "totalValue": sum(row["value"] for row in holdings),
            "holdings": holdings,
            "changes": build_changes(holdings, previous),
        }
        snapshots.append(snapshot)
        history[snapshot["period"]] = summarize_snapshot(snapshot)
        previous = holdings
        print(f"{manager_key} {snapshot['period']}: {len(holdings)} holdings, ${snapshot['totalValue'] / 1_000_000_000:.2f}B")
    history["_coreTrend"] = build_core_trend(snapshots)
    return history


def replace_history(html_text, history):
    replacement = "const INVESTOR_HISTORY = " + json.dumps(history, ensure_ascii=False) + ";"
    return re.sub(r"const INVESTOR_HISTORY = .*?;", replacement, html_text, count=1, flags=re.S)


def main():
    DATA_DIR.mkdir(exist_ok=True)
    history = {}
    for key, meta in MANAGERS.items():
        history[key] = build_manager_history(key, meta)
    for page in [ROOT / "investors.html", ROOT / "outputs" / "investors.html"]:
        page.write_text(replace_history(page.read_text(), history))
    print("built histories:", {key: len(value) for key, value in history.items()})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise

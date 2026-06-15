#!/usr/bin/env python3
import csv
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS = ROOT / "berkshire_submissions.json"
CIK = "1067983"
USER_AGENT = "fuguiplus 13f research fuguiplus@example.com"
START_DATE = "2016-06-30"


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._in_td = False
        self._cell = []
        self._row = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._in_td = True
            self._cell = []

    def handle_data(self, data):
        if self._in_td:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_td:
            text = " ".join("".join(self._cell).replace("\xa0", " ").split())
            self._row.append(text)
            self._in_td = False
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def clean_number(value):
    value = (value or "").replace(",", "").replace("$", "").strip()
    if not value or value in {"-", "None"}:
        return 0
    return int(float(value))


def period_from_date(report_date):
    year, _, day = report_date.split("-")
    quarter = {"03-31": "Q1", "06-30": "Q2", "09-30": "Q3", "12-31": "Q4"}[report_date[5:]]
    return f"{year} {quarter}"


def short_period(period):
    year, quarter = period.split()
    return f"{year[2:]}{quarter}"


def load_13f_filings():
    data = json.loads(SUBMISSIONS.read_text())
    recent = data["filings"]["recent"]
    filings = []
    seen_dates = set()
    for idx, form in enumerate(recent["form"]):
        report_date = recent["reportDate"][idx]
        if "13F" not in form or "/A" in form or report_date < START_DATE:
            continue
        if report_date in seen_dates:
            continue
        seen_dates.add(report_date)
        accession = recent["accessionNumber"][idx]
        filings.append({
            "form": form,
            "reportDate": report_date,
            "filingDate": recent["filingDate"][idx],
            "accession": accession,
            "accessionCompact": accession.replace("-", ""),
        })
    return sorted(filings, key=lambda item: item["reportDate"])


def local_xml_path(filing):
    pattern = f"berkshire_{filing['reportDate']}_{filing['accessionCompact']}_13f.xml"
    return ROOT / pattern


def download_if_missing(filing):
    path = local_xml_path(filing)
    if path.exists():
        return path
    accession = filing["accessionCompact"]
    index_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{accession}/index.json"
    req = urllib.request.Request(index_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        index = json.loads(resp.read().decode("utf-8"))
    names = [item["name"] for item in index["directory"]["item"]]
    xml_name = next((name for name in names if name.lower() == "form13finfotable.xml"), None)
    if not xml_name:
        xml_name = next((name for name in names if "infotable" in name.lower() and name.lower().endswith(".xml")), None)
    if not xml_name:
        raise RuntimeError(f"No information table XML for {filing['reportDate']} {filing['accession']}")
    xml_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{accession}/{xml_name}"
    req = urllib.request.Request(xml_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        path.write_bytes(resp.read())
    (ROOT / f"sec_index_{filing['reportDate']}_{accession}.json").write_text(json.dumps(index, indent=2))
    return path


def parse_xml(path):
    text = path.read_text(errors="ignore")
    if re.search(r"<(?:[\w.-]+:)?infoTable\b", text, re.I):
        return parse_structured_xml(text)
    return parse_html_table(text)


def tag_text(block, tag):
    match = re.search(rf"<(?:\w+:)?{tag}\b[^>]*>(.*?)</(?:\w+:)?{tag}>", block, re.I | re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() if match else ""


def parse_structured_xml(text):
    def local_name(tag):
        return tag.rsplit("}", 1)[-1].split(":", 1)[-1]

    def first_text(node, wanted):
        for child in node.iter():
            if local_name(child.tag) == wanted and child.text:
                return child.text.strip()
        return ""

    rows = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        root = None

    if root is not None:
        for node in root.iter():
            if local_name(node.tag) != "infoTable":
                continue
            rows.append({
                "issuer": first_text(node, "nameOfIssuer").upper(),
                "class": first_text(node, "titleOfClass").upper(),
                "cusip": first_text(node, "cusip").upper(),
                "put_call": first_text(node, "putCall").upper(),
                "value": clean_number(first_text(node, "value")),
                "shares": clean_number(first_text(node, "sshPrnamt")),
                "lines": first_text(node, "otherManager"),
            })
        return normalize_values(rows)

    blocks = re.findall(r"<(?:[\w.-]+:)?infoTable\b[^>]*>(.*?)</(?:[\w.-]+:)?infoTable>", text, re.I | re.S)
    for block in blocks:
        rows.append({
            "issuer": tag_text(block, "nameOfIssuer").upper(),
            "class": tag_text(block, "titleOfClass").upper(),
            "cusip": tag_text(block, "cusip").upper(),
            "put_call": tag_text(block, "putCall").upper(),
            "value": clean_number(tag_text(block, "value")),
            "shares": clean_number(tag_text(block, "sshPrnamt")),
            "lines": tag_text(block, "otherManager"),
        })
    return normalize_values(rows)


def parse_html_table(text):
    parser = TableParser()
    parser.feed(text)
    rows = []
    for cells in parser.rows:
        if len(cells) < 7:
            continue
        if cells[0].upper() in {"NAME OF ISSUER", "ISSUER"}:
            continue
        if not re.match(r"^[A-Z0-9]{6,9}$", cells[2] or ""):
            continue
        rows.append({
            "issuer": cells[0].upper(),
            "class": cells[1].upper(),
            "cusip": cells[2].upper(),
            "put_call": cells[3].upper() if len(cells) > 3 else "",
            "value": clean_number(cells[4]),
            "shares": clean_number(cells[5]),
            "lines": cells[9] if len(cells) > 9 else "",
        })
    return normalize_values(rows)


def normalize_values(rows):
    grouped = {}
    for row in rows:
        key = (row["cusip"], row["put_call"])
        if key not in grouped:
            grouped[key] = {**row, "lineRefs": []}
        else:
            grouped[key]["value"] += row["value"]
            grouped[key]["shares"] += row["shares"]
        if row.get("lines"):
            grouped[key]["lineRefs"].append(str(row["lines"]))
    rows = []
    for row in grouped.values():
        line_refs = sorted({part.strip() for ref in row.pop("lineRefs") for part in ref.split(",") if part.strip()})
        row["lines"] = ",".join(line_refs)
        rows.append(row)
    total = sum(row["value"] for row in rows)
    if total and total < 1_000_000_000:
        for row in rows:
            row["value"] *= 1000
    return sorted(rows, key=lambda row: row["value"], reverse=True)


def build_changes(current, previous):
    previous_by_key = {(row["cusip"], row["put_call"]): row for row in previous or []}
    current_by_key = {(row["cusip"], row["put_call"]): row for row in current}
    keys = sorted(set(previous_by_key) | set(current_by_key))
    changes = []
    for key in keys:
        prev = previous_by_key.get(key)
        cur = current_by_key.get(key)
        ref = cur or prev
        changes.append({
            "issuer": ref["issuer"],
            "class": ref["class"],
            "cusip": ref["cusip"],
            "put_call": ref["put_call"],
            "prev_shares": prev["shares"] if prev else 0,
            "cur_shares": cur["shares"] if cur else 0,
            "delta_shares": (cur["shares"] if cur else 0) - (prev["shares"] if prev else 0),
            "prev_value": prev["value"] if prev else 0,
            "cur_value": cur["value"] if cur else 0,
            "delta_value": (cur["value"] if cur else 0) - (prev["value"] if prev else 0),
        })
    return changes


def build_category_trend(snapshots):
    buckets = {
        "科技与互联网": ["APPLE", "ALPHABET", "AMAZON", "MICROSOFT", "VERISIGN"],
        "金融": ["BANK", "AMERICAN EXPRESS", "MOODYS", "GOLDMAN", "JPMORGAN", "VISA", "MASTERCARD", "ALLY", "CAPITAL ONE", "CHUBB", "AON"],
        "消费与品牌": ["COCA COLA", "KRAFT", "KROGER", "COSTCO", "RESTAURANT", "DOMINOS", "CONSTELLATION"],
        "能源与工业": ["CHEVRON", "OCCIDENTAL", "PHILLIPS", "SUNCOR", "NUCOR", "LOUISIANA PAC"],
    }
    series = []
    for category, keywords in buckets.items():
        points = []
        for snapshot in snapshots:
            value = sum(row["value"] for row in snapshot["holdings"] if any(key in row["issuer"] for key in keywords))
            points.append({
                "period": snapshot["period"],
                "shortPeriod": snapshot["shortPeriod"],
                "value": value,
                "weight": value / snapshot["totalValue"] if snapshot["totalValue"] else 0,
            })
        series.append({"category": category, "points": points})
    return {"series": series}


def build_trend_data(snapshots):
    periods = [
        {
            "period": snapshot["period"],
            "shortPeriod": snapshot["shortPeriod"],
            "reportDate": snapshot["reportDate"],
            "filingDate": snapshot["filingDate"],
            "totalValue": snapshot["totalValue"],
        }
        for snapshot in snapshots
    ]
    top_names = []
    for snapshot in reversed(snapshots):
        for row in snapshot["holdings"][:10]:
            if row["issuer"] not in top_names:
                top_names.append(row["issuer"])
            if len(top_names) >= 12:
                break
        if len(top_names) >= 12:
            break
    series = []
    for name in top_names:
        points = []
        for snapshot in snapshots:
            match = next((row for row in snapshot["holdings"] if row["issuer"] == name), None)
            value = match["value"] if match else 0
            points.append({
                "period": snapshot["period"],
                "shortPeriod": snapshot["shortPeriod"],
                "reportDate": snapshot["reportDate"],
                "value": value,
                "valueBillion": round(value / 100_000_000, 2),
                "weight": value / snapshot["totalValue"] if snapshot["totalValue"] else 0,
                "shares": match["shares"] if match else 0,
            })
        series.append({"name": name, "key": name, "points": points})
    return {"periods": periods, "series": series}


def write_csvs(latest_snapshot, previous_snapshot):
    with (ROOT / "berkshire_2026q1_holdings.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["issuer", "class", "cusip", "put_call", "value", "shares", "lines"])
        writer.writeheader()
        writer.writerows(latest_snapshot["holdings"])
    with (ROOT / "berkshire_2026q1_vs_2025q4_changes.csv").open("w", newline="") as fh:
        fieldnames = ["issuer", "class", "cusip", "put_call", "prev_shares", "cur_shares", "delta_shares", "prev_value", "cur_value", "delta_value"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(latest_snapshot["changes"])


def render_js(snapshots):
    latest = snapshots[-1]
    return "\n".join([
        "const HOLDINGS = " + json.dumps(latest["holdings"], ensure_ascii=False) + ";",
        "const CHANGES = " + json.dumps(latest["changes"], ensure_ascii=False) + ";",
        "const TREND_DATA = " + json.dumps(build_trend_data(snapshots), ensure_ascii=False) + ";",
        "const CATEGORY_TREND_DATA = " + json.dumps(build_category_trend(snapshots), ensure_ascii=False) + ";",
        "const PERIOD_SNAPSHOTS = " + json.dumps(snapshots, ensure_ascii=False) + ";",
        "",
    ])


def replace_embedded_data(html_text, data_js):
    start = html_text.index("    const HOLDINGS = ")
    end = html_text.index("    const managers = ", start)
    indented = "".join("    " + line + "\n" for line in data_js.splitlines())
    return html_text[:start] + indented + html_text[end:]


def main():
    filings = load_13f_filings()
    snapshots = []
    previous = None
    for filing in filings:
        path = download_if_missing(filing)
        holdings = parse_xml(path)
        total_value = sum(row["value"] for row in holdings)
        snapshot = {
            "period": period_from_date(filing["reportDate"]),
            "shortPeriod": short_period(period_from_date(filing["reportDate"])),
            "reportDate": filing["reportDate"],
            "filingDate": filing["filingDate"],
            "totalValue": total_value,
            "holdings": holdings,
            "changes": build_changes(holdings, previous),
        }
        snapshots.append(snapshot)
        previous = holdings
        print(f"{snapshot['period']}: {len(holdings)} holdings, ${total_value / 1_000_000_000:.2f}B")

    data_js = render_js(snapshots)
    (ROOT / "data_for_page.js").write_text(data_js)
    write_csvs(snapshots[-1], snapshots[-2])
    for page in [ROOT / "investors.html", ROOT / "outputs" / "investors.html"]:
        page.write_text(replace_embedded_data(page.read_text(), data_js))
    print(f"built {len(snapshots)} periods: {snapshots[0]['period']} - {snapshots[-1]['period']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise

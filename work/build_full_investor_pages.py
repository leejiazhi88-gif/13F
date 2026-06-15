#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path

from build_investor_history import (
    DATA_DIR,
    MANAGERS,
    build_core_trend,
    download_info_table,
    load_13f_filings,
    parse_table,
    ticker_guess,
)
from build_berkshire_data import ROOT, build_changes, period_from_date


OUT = ROOT / "outputs"
FULL_KEYS = ["himalaya", "pershing", "tci", "baupost"]
DISPLAY = {
    "himalaya": {
        "zh": "李录",
        "en": "Li Lu",
        "firm": "Himalaya Capital Management",
        "tag": "华人价值",
        "style": "价值投资、少数高确信度持仓",
        "focus": ["金融", "消费", "科技", "中美优质公司"],
        "note": "巴菲特/芒格体系下最值得长期跟踪的华人投资人之一。",
    },
    "pershing": {
        "zh": "比尔·阿克曼",
        "en": "Bill Ackman",
        "firm": "Pershing Square",
        "tag": "集中组合",
        "style": "高集中度、激进价值、品牌消费",
        "focus": ["消费", "餐饮", "地产", "平台公司"],
        "note": "持仓数量少、叙事清晰，适合做单独可视化页面。",
    },
    "tci": {
        "zh": "克里斯·霍恩",
        "en": "Chris Hohn",
        "firm": "TCI Fund Management",
        "tag": "质量价值",
        "style": "集中持仓、优质现金流、股东回报",
        "focus": ["交易所", "铁路", "评级", "支付"],
        "note": "组合通常很集中，适合观察质量资产的长期定价。",
    },
    "baupost": {
        "zh": "赛斯·卡拉曼",
        "en": "Seth Klarman",
        "firm": "Baupost Group",
        "tag": "深度价值",
        "style": "深度价值、特殊机会、低换手",
        "focus": ["价值股", "特殊机会", "现金替代", "周期"],
        "note": "仓位变化往往比单季持仓本身更有信息量。",
    },
}


def compact_holdings(rows):
    return [
        {
            "issuer": row["issuer"],
            "class": row["class"],
            "cusip": row["cusip"],
            "put_call": row.get("put_call", ""),
            "value": row["value"],
            "shares": row["shares"],
        }
        for row in rows
    ]


def compact_changes(rows):
    return [
        {
            "issuer": row["issuer"],
            "class": row["class"],
            "cusip": row["cusip"],
            "put_call": row.get("put_call", ""),
            "prev_shares": row["prev_shares"],
            "cur_shares": row["cur_shares"],
            "delta_shares": row["delta_shares"],
            "prev_value": row["prev_value"],
            "cur_value": row["cur_value"],
            "delta_value": row["delta_value"],
        }
        for row in rows
    ]


def build_snapshots(key, meta):
    previous = None
    snapshots = []
    for filing in load_13f_filings(meta["cik"]):
        path = download_info_table(key, meta["cik"], filing)
        holdings = parse_table(path)
        total = sum(row["value"] for row in holdings)
        period = period_from_date(filing["reportDate"])
        top10 = sum(row["value"] for row in holdings[:10]) / total * 100 if total else 0
        top = [
            {
                "label": ticker_guess(row),
                "issuer": row["issuer"],
                "value": row["value"],
                "weight": row["value"] / total if total else 0,
                "shares": row["shares"],
            }
            for row in holdings[:10]
        ]
        snapshots.append(
            {
                "period": period,
                "reportDate": filing["reportDate"],
                "filingDate": filing["filingDate"],
                "totalValue": total,
                "holdings": compact_holdings(holdings),
                "changes": compact_changes(build_changes(holdings, previous)),
                "top10": top10,
                "top": top,
            }
        )
        previous = holdings
    return snapshots


def html_escape(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_page(key, meta, snapshots):
    profile = DISPLAY[key]
    trend_source = [
        {
            "period": snap["period"],
            "reportDate": snap["reportDate"],
            "filingDate": snap["filingDate"],
            "totalValue": snap["totalValue"],
            "holdings": snap["holdings"],
        }
        for snap in snapshots
    ]
    data = {
        "profile": profile,
        "snapshots": snapshots,
        "coreTrend": build_core_trend(trend_source),
    }
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    focus = "".join(f"<span>{html_escape(item)}</span>" for item in profile["focus"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(profile["zh"])} 13F 完整页</title>
  <style>
    :root {{
      --bg:#f7f8fa; --surface:#fff; --text:#18212b; --muted:#66727f; --line:#dce2e8;
      --green:#117b5b; --blue:#2764a8; --red:#b33a3a; --amber:#9a6710; --ink:#0f1720;
      --shadow:0 14px 36px rgba(20,32,46,.08);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);letter-spacing:0}} a{{color:inherit}}
    .topbar{{position:sticky;top:0;z-index:20;background:rgba(247,248,250,.92);border-bottom:1px solid var(--line);backdrop-filter:blur(14px)}}
    .topbar-inner{{max-width:1240px;margin:0 auto;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;gap:18px}}
    .brand{{display:flex;align-items:center;gap:12px;min-width:0}} .mark{{width:40px;height:40px;border-radius:8px;background:var(--ink);color:white;display:grid;place-items:center;font-weight:800}}
    .brand h1{{margin:0;font-size:18px;line-height:1.25;color:var(--ink)}} .brand span{{display:block;margin-top:3px;color:var(--muted);font-size:12px}}
    .nav{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}} .nav a,.nav select{{border:1px solid var(--line);border-radius:8px;padding:9px 11px;background:var(--surface);text-decoration:none;color:var(--muted);font:inherit;font-size:13px;line-height:1}}
    main{{max-width:1240px;margin:0 auto;padding:24px}} .hero{{background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);padding:28px;display:grid;grid-template-columns:minmax(0,1.1fr) minmax(330px,.9fr);gap:22px;align-items:stretch}}
    .eyebrow{{display:inline-flex;gap:8px;align-items:center;color:var(--muted);font-size:13px;margin-bottom:16px}} .dot{{width:8px;height:8px;border-radius:50%;background:var(--green)}} h2{{margin:0;color:var(--ink);font-size:clamp(32px,4vw,56px);line-height:1.05}} .lead{{margin:18px 0 0;color:var(--muted);font-size:15px;line-height:1.65;max-width:780px}}
    .tags{{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}} .tags span{{border:1px solid var(--line);border-radius:999px;padding:5px 8px;color:var(--muted);background:#fbfcfd;font-size:12px}}
    .metrics{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}} .metric,.panel{{background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}} .metric{{padding:16px;min-height:112px;display:flex;flex-direction:column;justify-content:space-between}} .metric span{{color:var(--muted);font-size:12px}} .metric strong{{color:var(--ink);font-size:28px;line-height:1.1;font-variant-numeric:tabular-nums}}
    section{{margin-top:18px}} .panel{{padding:18px}} .chart-panel{{padding:0;overflow:hidden}} .section-head,.chart-head{{display:flex;justify-content:space-between;gap:16px;align-items:flex-end;margin-bottom:12px}} .chart-head{{padding:18px 20px 0;margin-bottom:0}} .section-head h3,.chart-head h3{{margin:0;color:var(--ink);font-size:20px}} .section-head p,.chart-head p{{margin:5px 0 0;color:var(--muted);font-size:13px;line-height:1.5}}
    .chart{{display:block;width:100%;height:390px}} .grid-line{{stroke:#dfe6ee;stroke-width:1}} .axis-label{{fill:var(--muted);font-size:12px;font-weight:650}} .line{{fill:none;stroke-width:2.3;stroke-linecap:round;stroke-linejoin:round}} .dot-point{{stroke:white;stroke-width:1.4}}
    .legend{{border-top:1px solid var(--line);padding:12px 18px 16px;display:flex;gap:10px 16px;flex-wrap:wrap;color:#43566f;font-size:12px}} .legend span{{display:inline-flex;align-items:center;gap:7px}} .swatch{{width:10px;height:10px;border-radius:3px;flex:0 0 auto}}
    .chart-narrative{{border-top:1px solid var(--line);padding:14px 16px 16px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;background:#fbfcfd}} .narrative-card{{border:1px solid var(--line);border-radius:8px;background:var(--surface);padding:12px;min-height:112px}} .narrative-card b{{display:block;color:var(--ink);font-size:13px;margin-bottom:6px}} .narrative-card p{{margin:0;color:var(--muted);font-size:12px;line-height:1.55}}
    .grid-2{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px}} .bars{{display:grid;gap:10px}} .bar-row{{display:grid;grid-template-columns:minmax(0,180px) minmax(0,1fr) auto;gap:10px;align-items:center;font-size:13px;color:var(--muted)}} .bar-name{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text);font-weight:650}} .bar-track{{height:9px;border-radius:999px;background:#edf1f5;overflow:hidden}} .bar-fill{{height:100%;border-radius:999px}} .bar-value{{font-variant-numeric:tabular-nums}}
    .table-actions{{display:flex;gap:8px;flex-wrap:wrap}} .table-actions button{{border:1px solid var(--line);background:white;color:var(--muted);border-radius:8px;padding:8px 10px;font:inherit;font-size:12px;cursor:pointer}} .table-actions button.active{{background:var(--ink);color:white;border-color:var(--ink)}} .table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:8px}} table{{width:100%;border-collapse:collapse;min-width:760px}} th,td{{border-bottom:1px solid var(--line);padding:10px 12px;text-align:left;font-size:13px;vertical-align:top}} th{{color:var(--muted);font-size:12px;background:#fbfcfd;position:sticky;top:0}} td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}} tr:last-child td{{border-bottom:0}} .change-tag{{border-radius:999px;padding:4px 7px;font-size:12px;display:inline-block}} .add{{color:var(--green);background:#dff3eb}} .cut{{color:var(--amber);background:#f6ecd8}} .exit{{color:var(--red);background:#f8e6e3}} .keep{{color:var(--muted);background:#edf1f5}}
    @media(max-width:820px){{.topbar-inner{{align-items:flex-start;flex-direction:column}}.nav{{justify-content:flex-start;width:100%}}main{{padding:16px}}.hero,.grid-2{{grid-template-columns:1fr}}.metrics{{grid-template-columns:1fr}}.chart{{height:320px}}.chart-narrative{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
  <header class="topbar"><div class="topbar-inner"><div class="brand"><div class="mark">13F</div><div><h1>{html_escape(profile["zh"])} 13F 完整页</h1><span>{html_escape(profile["firm"])} · 原始表聚合</span></div></div><nav class="nav"><select id="period-select" aria-label="选择报告期"></select><a href="investors.html">返回一览</a></nav></div></header>
  <main>
    <section class="hero"><div><div class="eyebrow"><i class="dot"></i>{html_escape(profile["tag"])} · {html_escape(profile["style"])}</div><h2>{html_escape(profile["zh"])}<br>{html_escape(profile["en"])}</h2><p class="lead">{html_escape(profile["note"])} 13F 只覆盖美国上市证券多头仓位和部分期权，不代表完整资产；除 Berkshire 外，现金/短债不在 13F 中披露。</p><div class="tags">{focus}</div></div><div class="metrics" id="metrics"></div></section>
    <section class="panel chart-panel"><div class="chart-head"><div><h3>核心持仓权重趋势</h3><p>最新前 6 大持仓回看历史季度；虚线为其他13F持仓，非现金口径。</p></div><p id="chart-range"></p></div><svg class="chart" id="trend-chart" role="img"></svg><div class="legend" id="legend"></div><div class="chart-narrative" id="trend-narrative"></div></section>
    <section class="grid-2"><div class="panel"><div class="section-head"><div><h3>前十大持仓分布</h3><p id="bar-caption"></p></div></div><div class="bars" id="bars"></div></div><div class="panel"><div class="section-head"><div><h3>跟踪口径</h3><p>与 Berkshire 页保持同一套控件：报告期、趋势、当前持仓、季度变动。</p></div></div><div id="facts"></div></div></section>
    <section class="panel"><div class="section-head"><div><h3>当前完整持仓表</h3><p>按证券口径聚合，市值单位为美元。</p></div></div><div class="table-wrap"><table><thead><tr><th>名称</th><th>类别 / CUSIP</th><th class="num">市值</th><th class="num">权重</th><th class="num">股数</th></tr></thead><tbody id="holdings-body"></tbody></table></div></section>
    <section class="panel"><div class="section-head"><div><h3>季度变动表</h3><p>与上一已接入季度比较。</p></div><div class="table-actions" id="change-filters"><button class="active" data-filter="focus">重点</button><button data-filter="all">全部</button><button data-filter="add">增仓/新进</button><button data-filter="cut">减仓</button><button data-filter="exit">清仓</button></div></div><div class="table-wrap"><table><thead><tr><th>名称</th><th>类型</th><th class="num">上期股数</th><th class="num">本期股数</th><th class="num">股数变化</th><th class="num">本期市值</th><th class="num">市值变化</th></tr></thead><tbody id="changes-body"></tbody></table></div></section>
  </main>
  <script>
    const DATA = {payload};
    const colors = ["#19212b","#117b5b","#2764a8","#9a6710","#b33a3a","#596a7a","#4d7c6f","#6e5d38"];
    const holdingNames = {{
      "ADOBE INC":"奥多比","AGILENT TECHNOLOGIES INC":"安捷伦科技","AIR PRODS & CHEMS INC":"空气产品与化学","ALIBABA GROUP HLDG LTD":"阿里巴巴","ALPHABET INC":"谷歌母公司","ALTABA INC":"Altaba","AMAZON COM INC":"亚马逊","AMERICAN INTL GROUP INC":"美国国际集团","APPLE INC":"苹果","APPLIED MATLS INC":"应用材料","AON PLC":"怡安","AUTODESK INC":"欧特克","AUTOMATIC DATA PROCESSING IN":"自动数据处理公司","BAIDU INC":"百度","BERKSHIRE HATHAWAY INC":"伯克希尔哈撒韦","BERKSHIRE HATHAWAY INC DEL":"伯克希尔哈撒韦","BK OF AMERICA CORP":"美国银行","BLACKSTONE GROUP INC":"黑石集团","BLOCK H & R INC":"H&R Block","BRISTOL MYERS SQUIBB CO":"百时美施贵宝","BROOKFIELD CORP":"布鲁克菲尔德","CANADIAN NATL RY CO":"加拿大国家铁路","CANADIAN PAC RY LTD":"加拿大太平洋铁路","CANADIAN PACIFIC KANSAS CITY":"加拿大太平洋堪萨斯城铁路","CHARTER COMMUNICATIONS INC":"Charter 通信","CHARTER COMMUNICATIONS INC N":"Charter 通信","CHIPOTLE MEXICAN GRILL INC":"Chipotle 墨西哥烧烤","CITIGROUP INC":"花旗集团","COINBASE GLOBAL INC":"Coinbase","COMCAST CORP NEW":"康卡斯特","CROCS INC":"卡骆驰","DELL TECHNOLOGIES INC":"戴尔科技","DISNEY WALT CO":"华特迪士尼","DOMINOS PIZZA INC":"达美乐披萨","DROPBOX INC":"Dropbox","EAST WEST BANCORP INC":"华美银行","EBAY INC":"eBay","EBAY INC.":"eBay","ELEVANCE HEALTH INC":"Elevance Health","ELEVANCE HEALTH INC FORMERLY":"Elevance Health","EQUIFAX INC":"益博睿/Equifax","FACEBOOK INC":"Meta/Facebook","FERGUSON PLC NEW":"Ferguson","FERGUSON ENTERPRISES INC":"Ferguson","FIDELITY NATL INFORMATION SV":"FIS 金融信息服务","FISERV INC":"Fiserv","FOX CORP":"福克斯","GE AEROSPACE":"GE 航空航天","GENERAL ELECTRIC CO":"通用电气","GDS HLDGS LTD":"万国数据","HCA HEALTHCARE INC":"HCA 医疗","HERTZ GLOBAL HLDGS INC":"赫兹租车","HILTON WORLDWIDE HLDGS INC":"希尔顿全球","HOWARD HUGHES CORP":"霍华德休斯","HOWARD HUGHES HOLDINGS INC":"霍华德休斯控股","HP INC":"惠普","HUMANA INC":"哈门那","INTEL CORP":"英特尔","JAZZ PHARMACEUTICALS PLC":"Jazz 制药","KLA CORP":"科磊","LAM RESEARCH CORP":"泛林集团","LIBERTY BROADBAND CORP":"Liberty Broadband","LIBERTY GLOBAL LTD":"Liberty Global","LIBERTY GLOBAL PLC":"Liberty Global","LIBERTY MEDIA CORP DEL":"Liberty Media","LIBERTY MEDIA CORP DELAWARE":"Liberty Media","LINDE PLC":"林德","LOWES COS INC":"劳氏","MASTERCARD INC":"万事达卡","MASTERCARD INCORPORATED":"万事达卡","MCDERMOTT INTL INC":"McDermott","MCKESSON CORP":"麦克森","META PLATFORMS INC":"Meta 平台","MICRON TECHNOLOGY INC":"美光科技","MICROSOFT CORP":"微软","MONDELEZ INTL INC":"亿滋国际","MOODYS CORP":"穆迪","MSCI INC":"MSCI 明晟","NETFLIX INC":"奈飞","NIKE INC":"耐克","NOMAD FOODS LTD":"Nomad Foods","NOMAD HLDGS LTD":"Nomad Foods","NORFOLK SOUTHERN CORP":"诺福克南方铁路","NORTHROP GRUMMAN CORP":"诺斯罗普·格鲁曼","OCCIDENTAL PETE CORP":"西方石油","PDD HOLDINGS INC":"拼多多控股","PINDUODUO INC":"拼多多","PG&E CORP":"太平洋煤电","RAYTHEON CO":"雷神","RAYTHEON TECHNOLOGIES CORP":"雷神技术","RESTAURANT BRANDS INTL INC":"餐饮品牌国际","S&P GLOBAL INC":"标普全球","SABLE OFFSHORE CORP":"Sable Offshore","SEAPORT ENTMT GROUP INC":"Seaport Entertainment","SINA CORP":"新浪","STARBUCKS CORP":"星巴克","TENCENT MUSIC ENTMT GROUP":"腾讯音乐","THERMO FISHER SCIENTIFIC INC":"赛默飞世尔","TRANSDIGM GROUP INC":"TransDigm","UBER TECHNOLOGIES INC":"优步","UNION PAC CORP":"联合太平洋铁路","UNION PACIFIC CORP":"联合太平洋铁路","VISA INC":"Visa","WEIBO CORP":"微博","WESCO INTL INC":"WESCO","ZOETIS INC":"硕腾"
    }};
    let activePeriod = DATA.snapshots[DATA.snapshots.length - 1].period;
    let activeFilter = "focus";
    function amount(value) {{ if (!Number.isFinite(value)) return "-"; if (Math.abs(value)>=1e9) return "$"+(value/1e9).toFixed(2)+"B"; if (Math.abs(value)>=1e6) return "$"+(value/1e6).toFixed(2)+"M"; return "$"+value.toLocaleString("en-US"); }}
    function shares(value) {{ return Number(value || 0).toLocaleString("en-US"); }}
    function pct(value) {{ return (value*100).toFixed(1)+"%"; }}
    function short(period) {{ return period.replace("20","").replace(" Q","Q"); }}
    function normalizeIssuer(name) {{ return String(name || "").replace(/\\s+/g," ").trim().replace(/\\b(CL|CLASS|COM|NEW|DEL|FORMERLY|HLDG|HLDGS|CORP|INC|LTD|PLC|CO)\\b.*$/,"").trim(); }}
    function issuerCn(name) {{ return holdingNames[name] || holdingNames[normalizeIssuer(name)] || ""; }}
    function issuerName(name) {{ if (name === "其他13F持仓") return name; const cn=issuerCn(name); return cn ? `${{name}}（${{cn}}）` : name; }}
    function snap() {{ return DATA.snapshots.find(item => item.period === activePeriod) || DATA.snapshots[DATA.snapshots.length - 1]; }}
    function type(row) {{ if (row.prev_shares === 0 && row.cur_shares > 0) return "新进"; if (row.cur_shares === 0 && row.prev_shares > 0) return "清仓"; if (row.delta_shares > 0) return "增仓"; if (row.delta_shares < 0) return "减仓"; return "不变"; }}
    function typeClass(value) {{ return {{"新进":"add","增仓":"add","减仓":"cut","清仓":"exit","不变":"keep"}}[value]; }}
    function renderSelect() {{ const select=document.getElementById("period-select"); select.innerHTML=DATA.snapshots.map(item=>`<option value="${{item.period}}">${{item.period}} · ${{item.reportDate}}</option>`).join(""); select.value=activePeriod; select.addEventListener("change",()=>{{activePeriod=select.value; renderAll(); renderChart();}}); }}
    function renderMetrics() {{ const s=snap(); document.getElementById("metrics").innerHTML=[["13F 市值",amount(s.totalValue)],["持仓数量",String(s.holdings.length)],["前十大集中度",s.top10.toFixed(1)+"%"],["提交日",s.filingDate]].map(([k,v])=>`<div class="metric"><span>${{k}}</span><strong>${{v}}</strong></div>`).join(""); }}
    function renderFacts() {{ const s=snap(); document.getElementById("facts").innerHTML=`<div style="display:grid;gap:11px;color:var(--muted);font-size:14px;line-height:1.55"><div><b style="color:var(--text)">申报主体：</b>${{DATA.profile.firm}}</div><div><b style="color:var(--text)">报告期：</b>${{s.reportDate}}</div><div><b style="color:var(--text)">提交日：</b>${{s.filingDate}}</div><div><b style="color:var(--text)">现金口径：</b>13F 不披露现金/短债；虚线“其他13F持仓”只是未进入前 6 大核心线的已披露证券。</div></div>`; }}
    function renderBars() {{ const s=snap(); const max=s.top[0]?.value || 1; document.getElementById("bar-caption").textContent=s.period+" · 前十大"; document.getElementById("bars").innerHTML=s.top.slice(0,10).map((row,index)=>`<div class="bar-row"><div class="bar-name" title="${{issuerName(row.issuer)}}">${{index+1}}. ${{issuerName(row.issuer)}}</div><div class="bar-track"><div class="bar-fill" style="width:${{Math.max(2,row.value/max*100)}}%;background:${{colors[index%colors.length]}}"></div></div><div class="bar-value">${{pct(row.weight)}}</div></div>`).join(""); }}
    function renderHoldings() {{ const s=snap(); document.getElementById("holdings-body").innerHTML=s.holdings.map(row=>`<tr><td><strong title="${{issuerName(row.issuer)}}">${{issuerName(row.issuer)}}</strong></td><td>${{row.class}}<br><span style="color:var(--muted);font-size:12px">${{row.cusip}}</span></td><td class="num">${{amount(row.value)}}</td><td class="num">${{pct(row.value/s.totalValue)}}</td><td class="num">${{shares(row.shares)}}</td></tr>`).join(""); }}
    function filteredChanges() {{ const rows=[...snap().changes]; if(activeFilter==="all") return rows.sort((a,b)=>Math.abs(b.delta_value)-Math.abs(a.delta_value)); if(activeFilter==="add") return rows.filter(r=>r.delta_shares>0).sort((a,b)=>b.cur_value-a.cur_value); if(activeFilter==="cut") return rows.filter(r=>r.delta_shares<0&&r.cur_shares>0).sort((a,b)=>Math.abs(b.delta_shares)-Math.abs(a.delta_shares)); if(activeFilter==="exit") return rows.filter(r=>r.cur_shares===0&&r.prev_shares>0).sort((a,b)=>b.prev_value-a.prev_value); return rows.filter(r=>r.delta_shares!==0).sort((a,b)=>Math.abs(b.delta_value)-Math.abs(a.delta_value)).slice(0,18); }}
    function renderChanges() {{ document.getElementById("changes-body").innerHTML=filteredChanges().map(row=>{{ const t=type(row); return `<tr><td><strong title="${{issuerName(row.issuer)}}">${{issuerName(row.issuer)}}</strong><br><span style="color:var(--muted);font-size:12px">${{row.class}} · ${{row.cusip}}</span></td><td><span class="change-tag ${{typeClass(t)}}">${{t}}</span></td><td class="num">${{shares(row.prev_shares)}}</td><td class="num">${{shares(row.cur_shares)}}</td><td class="num">${{row.delta_shares>0?"+":""}}${{shares(row.delta_shares)}}</td><td class="num">${{amount(row.cur_value)}}</td><td class="num">${{row.delta_value>0?"+":""}}${{amount(row.delta_value)}}</td></tr>`; }}).join(""); }}
    function pathFor(points) {{ let segments=[],cur=[]; points.forEach(p=>{{ if(p.value==null){{ if(cur.length)segments.push(cur); cur=[]; }} else cur.push(p); }}); if(cur.length)segments.push(cur); return segments.map(seg=>seg.map((p,i)=>`${{i?"L":"M"}} ${{p.x}} ${{p.y}}`).join(" ")).join(" "); }}
    function renderTrendNarrative(series, periods) {{ const activeIndex=periods.findIndex(period=>period.period===activePeriod); if(activeIndex<=0) return; const currentPeriod=periods[activeIndex].period; const previousPeriod=periods[activeIndex-1].period; const rows=series.map(row=>{{ const current=row.points.find(point=>point.period===currentPeriod); const previous=row.points.find(point=>point.period===previousPeriod); if(!current||!previous||current.weight==null||previous.weight==null) return null; return {{row,current,previous,delta:current.weight-previous.weight,valueDelta:(current.value||0)-(previous.value||0)}}; }}).filter(Boolean); if(!rows.length) return; const sorted=[...rows].sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta)); const biggest=sorted[0]; const risers=rows.filter(item=>item.delta>0).sort((a,b)=>b.delta-a.delta); const fallers=rows.filter(item=>item.delta<0).sort((a,b)=>a.delta-b.delta); const concentration=series.filter(row=>row.kind!=="remainder").reduce((sum,row)=>{{ const point=row.points.find(item=>item.period===currentPeriod); return sum+(point&&point.weight?point.weight:0); }},0); const biggestName=issuerName(biggest.row.name); const biggestMove=`${{biggestName}}${{biggest.delta>=0?"上升":"下降"}} ${{Math.abs(biggest.delta*100).toFixed(1)}} 个百分点`; const riseText=risers.length?`上升项：${{risers.slice(0,2).map(item=>`${{issuerName(item.row.name)}} +${{(item.delta*100).toFixed(1)}}pp`).join("、")}}。`:"没有明显上升项。"; const fallText=fallers.length?`下降项：${{fallers.slice(0,2).map(item=>`${{issuerName(item.row.name)}} ${{(item.delta*100).toFixed(1)}}pp`).join("、")}}。`:"没有明显下降项。"; const cause="这里展示的是 13F 已披露证券内部的权重变化；“其他13F持仓”不是现金，真实现金/空仓无法从 13F 直接读取。权重变化通常来自买卖和季度末价格重估的叠加。"; const outlook=fallers.length&&risers.length?`下个 Q 重点看 ${{issuerName(fallers[0].row.name)}} 的下降是否延续，以及 ${{issuerName(risers[0].row.name)}} 的上升是新增/加仓还是价格修复。`:`下个 Q 重点看 ${{biggestName}} 是否反向修复，以及前 6 大合计集中度是否继续维持在 ${{(concentration*100).toFixed(1)}}% 附近。`; document.getElementById("trend-narrative").innerHTML=`<div class="narrative-card"><b>最近这个 Q 发生了什么</b><p>${{currentPeriod}} 相比 ${{previousPeriod}}，核心曲线里最大变化是 ${{biggestMove}}。${{riseText}} ${{fallText}}</p></div><div class="narrative-card"><b>背后的可能根因</b><p>${{cause}}</p></div><div class="narrative-card"><b>下个 Q 的观察点</b><p>${{outlook}} 同时结合完整持仓表里的新进、清仓和股数变化验证。</p></div>`; }}
    function renderChart() {{ const periods=DATA.coreTrend.periods; const series=DATA.coreTrend.series.slice(0,6); series.push({{name:"其他13F持仓",kind:"remainder",points:periods.map(period=>{{ const visible=series.reduce((sum,row)=>{{ const p=row.points.find(item=>item.period===period.period); return sum+(p?p.value:0); }},0); const value=Math.max(0,(period.totalValue||0)-visible); return {{period:period.period,reportDate:period.reportDate,value,weight:period.totalValue?value/period.totalValue:null}}; }})}}); const width=1120,height=370,pad={{left:52,right:20,top:24,bottom:50}},plotW=width-pad.left-pad.right,plotH=height-pad.top-pad.bottom; const vals=series.flatMap(r=>r.points.map(p=>p.weight||0)); const max=Math.max(.55,Math.max(...vals)*1.06); const x=i=>pad.left+(periods.length===1?0:i/(periods.length-1)*plotW); const y=v=>pad.top+(1-v/max)*plotH; const ticks=[0,.25,.5,.75,1].map(r=>r*max); const step=Math.max(1,Math.ceil(periods.length/10)); const grid=ticks.map(t=>`<line class="grid-line" x1="${{pad.left}}" x2="${{width-pad.right}}" y1="${{y(t).toFixed(1)}}" y2="${{y(t).toFixed(1)}}"></line><text class="axis-label" x="${{pad.left-10}}" y="${{y(t)+4}}" text-anchor="end">${{Math.round(t*100)}}%</text>`).join(""); const lines=series.map((row,idx)=>{{ const color=colors[idx%colors.length]; const pts=periods.map((period,i)=>{{ const p=row.points.find(item=>item.period===period.period); const value=p?p.weight:null; return {{x:x(i).toFixed(1),y:value==null?null:y(value).toFixed(1),value,amount:p?p.value:0,period:period.period}}; }}); const dash=row.kind==="remainder"?'stroke-dasharray="7 6"':""; const label=issuerName(row.name); return `<path class="line" d="${{pathFor(pts)}}" stroke="${{color}}" ${{dash}}><title>${{label}} 权重趋势</title></path>${{pts.filter(p=>p.value!=null).map(p=>`<circle class="dot-point" cx="${{p.x}}" cy="${{p.y}}" r="${{row.kind==="remainder"?"4.2":"3.6"}}" fill="${{color}}"><title>${{label}}\\n${{p.period}}\\n权重：${{(p.value*100).toFixed(1)}}%\\n市值：${{amount(p.amount)}}${{row.kind==="remainder"?"\\n13F不披露现金，不能等同现金/空仓":""}}</title></circle>`).join("")}}`; }}).join(""); const labels=periods.map((p,i)=>(i===0||i===periods.length-1||i%step===0)?`<text class="axis-label" x="${{x(i).toFixed(1)}}" y="${{height-16}}" text-anchor="middle">${{short(p.period)}}</text>`:"").join(""); const svg=document.getElementById("trend-chart"); svg.setAttribute("viewBox",`0 0 ${{width}} ${{height}}`); svg.innerHTML=`<rect x="0" y="0" width="${{width}}" height="${{height}}" fill="transparent"></rect>${{grid}}${{lines}}${{labels}}`; document.getElementById("legend").innerHTML=series.map((row,i)=>`<span title="${{row.kind==="remainder"?"13F不披露现金，不能等同现金/空仓":issuerName(row.name)}}"><i class="swatch" style="background:${{colors[i%colors.length]}}"></i>${{issuerName(row.name)}}</span>`).join(""); document.getElementById("chart-range").textContent=periods.length?`${{short(periods[0].period)}}-${{short(periods[periods.length-1].period)}}`:""; renderTrendNarrative(series, periods); }}
    function renderAll() {{ renderMetrics(); renderFacts(); renderBars(); renderHoldings(); renderChanges(); }}
    document.getElementById("change-filters").querySelectorAll("button").forEach(btn=>btn.addEventListener("click",()=>{{ document.getElementById("change-filters").querySelectorAll("button").forEach(item=>item.classList.remove("active")); btn.classList.add("active"); activeFilter=btn.dataset.filter; renderChanges(); }}));
    renderSelect(); renderAll(); renderChart();
  </script>
</body>
</html>"""


def main():
    DATA_DIR.mkdir(exist_ok=True)
    for key in FULL_KEYS:
        snapshots = build_snapshots(key, MANAGERS[key])
        (OUT / f"investor_{key}.html").write_text(render_page(key, MANAGERS[key], snapshots))
        print(f"wrote investor_{key}.html with {len(snapshots)} periods")


if __name__ == "__main__":
    main()

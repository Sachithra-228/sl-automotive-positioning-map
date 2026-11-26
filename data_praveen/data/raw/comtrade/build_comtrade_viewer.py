#!/usr/bin/env python
"""Build 00_comtrade_viewer.html from every <HS>_<M|X>_<YEAR>.json in this folder.

Usage (run from anywhere):
    python build_comtrade_viewer.py            # rebuild once
    python build_comtrade_viewer.py --watch    # rebuild automatically whenever a file is added/changed

Drop a newly downloaded Comtrade JSON in this folder and re-run (or keep --watch
running); the HTML picks up new HS codes, years and partners with no code change.
The HTML is self-contained (data embedded) except for the Plotly CDN script.
"""
import json, re, sys, time, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "00_comtrade_viewer.html"  # "00_" keeps it at the top of the folder listing
FILE_RE = re.compile(r"^(\d{4,6})_([MX])_(\d{4})\.json$")

# Plain-English names for HS codes we have collected. Unknown codes fall back to "HS <code>".
HS_NAMES = {
    "4011": "New pneumatic rubber tyres",
    "8507": "Electric accumulators (batteries, incl. Li-ion)",
    "854430": "Ignition / vehicle wiring harness sets",
    "8701": "Tractors",
    "8702": "Buses (10+ persons)",
    "8703": "Passenger cars (all)",
    "870340": "Cars: petrol hybrid (non plug-in)",
    "870350": "Cars: diesel hybrid (non plug-in)",
    "870360": "Cars: petrol plug-in hybrid",
    "870370": "Cars: diesel plug-in hybrid",
    "870380": "Cars: fully electric (BEV)",
    "8704": "Goods vehicles / trucks",
    "8705": "Special-purpose vehicles",
    "8708": "Motor-vehicle parts & accessories",
    "8711": "Motorcycles (all)",
    "871160": "Electric motorcycles",
    "940120": "Motor-vehicle seats",
}
FLOW = {"M": "Import", "X": "Export"}

COLUMNS = [  # (field, meaning)
    ("period / refYear", "Year of the trade data (annual frequency)."),
    ("reporterCode = 144", "Reporting country: Sri Lanka."),
    ("flowCode", "M = Import into Sri Lanka, X = Export from Sri Lanka."),
    ("cmdCode", "HS commodity code (4 or 6 digits). More digits = narrower product."),
    ("partnerCode", "Trading partner. 0 = World total (sum of all partners)."),
    ("partner2Code / customsCode / motCode", "Second partner, customs regime, mode of transport. Here always 0 / C00 / 0 = no extra breakdown."),
    ("qty / qtyUnitCode", "Quantity and its unit (5 = number of items, 8 = kg, etc.). Missing for some products."),
    ("netWgt", "Net weight in kg."),
    ("primaryValue (cifvalue / fobvalue)", "Trade value in US dollars. Imports are CIF, exports FOB."),
    ("isAggregate", "True if the row is a rolled-up total rather than a single partner."),
    ("isQtyEstimated / isNetWgtEstimated", "Comtrade estimated the quantity or weight rather than the country reporting it."),
]



# ---- Brand tab inputs --------------------------------------------------------------------------
MASTER_CSV = HERE.parents[3] / "data" / "processed" / "master_sl_automotive.csv"
# Comtrade partner codes: China 156, Japan 392, India 699, Germany 276, Thailand 764
# ASSUMPTION (edit freely): where each brand's vehicles are mainly built/shipped from.
BRAND_ORIGIN = {
    "Toyota": [392, 764, 699], "Nissan": [392, 699], "Mercedes-Benz": [276], "Tata": [699], "Mahindra": [699],
    "MG": [156, 699, 764],
    **{b: [156] for b in ["BYD", "JAECOO", "Jetour", "GWM", "Wuling", "BAW", "OMODA", "Dongfeng", "SRM", "Kaiyi", "Leapmotor", "JAC"]},
}
# logo hints: simpleicons slug + colour, or built-in inline svg key, else text badge
BRAND_LOGO = {
    "Toyota": dict(slug="toyota", color="EB0A1E"), "MG": dict(slug="mg", color="C8102E"),
    "Tata": dict(slug="tata", color="486AAE"), "Mahindra": dict(slug="mahindra", color="DD052B"),
    "Nissan": dict(slug="nissan", color="C3002F"), "BYD": dict(svg="byd"), "Mercedes-Benz": dict(svg="mercedes"),
}
COMMERCIAL = {"Pickup": "8704", "Double Cab Pickup": "8704", "Light Truck": "8704", "Van": "8704", "Bus": "8702"}
HYBRID_CODES = ["870340", "870350", "870360", "870370"]


def load_brands():
    import csv
    if not MASTER_CSV.exists():
        return []
    brands = {}
    with MASTER_CSV.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            b = r["Brand"].strip()
            e = brands.setdefault(b, dict(name=b, distributors=set(), models=[]))
            e["distributors"].add(r["Distributor"].strip())
            body, pt = r["Body_Type"].strip(), r["Powertrain"].strip()
            if body in COMMERCIAL:
                hs = COMMERCIAL[body]
            elif pt == "EV":
                hs = "870380"
            elif pt == "Hybrid":
                hs = "HYBRID"
            else:
                hs = "8703"
            try:
                price = float(r["Std_Price_Mn"])
            except (ValueError, TypeError):
                price = None
            e["models"].append([r["Model"].strip(), pt, body, price, hs])
    out = []
    for b, e in sorted(brands.items(), key=lambda kv: -len(kv[1]["models"])):
        e["distributors"] = sorted(e["distributors"])
        e["origin"] = BRAND_ORIGIN.get(b, [])
        e["logo"] = BRAND_LOGO.get(b, {})
        out.append(e)
    return out


def load_partners():
    p = HERE / "reference_partnerAreas.json"
    if not p.exists():
        return {0: "World"}
    res = json.loads(p.read_text(encoding="utf-8")).get("results", [])
    m = {int(r["PartnerCode"]): r["PartnerDesc"] for r in res}
    m[0] = "World"
    return m


def build():
    partners = load_partners()
    files, rows = [], []
    for f in sorted(HERE.glob("*.json")):
        m = FILE_RE.match(f.name)
        if not m:
            continue
        hs, fl, yr = m.group(1), m.group(2), int(m.group(3))
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # corrupt download
            files.append(dict(file=f.name, hs=hs, flow=FLOW[fl], year=yr, n=0, status="unreadable: %s" % e,
                              modified=datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="minutes")))
            continue
        recs = d.get("data") or []
        files.append(dict(file=f.name, hs=hs, flow=FLOW[fl], year=yr, n=len(recs),
                          status="ok" if recs else "empty (API returned no data)",
                          error=d.get("error", ""), kb=round(f.stat().st_size / 1024, 1),
                          modified=datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="minutes")))
        for r in recs:
            pc = int(r.get("partnerCode") or 0)
            rows.append([yr, FLOW[fl], hs, pc, partners.get(pc, "code %d" % pc),
                         r.get("qty"), r.get("qtyUnitCode"), r.get("netWgt"), r.get("primaryValue"),
                         1 if r.get("isQtyEstimated") else 0])
    payload = dict(
        built=datetime.datetime.now().isoformat(timespec="seconds"),
        files=files, rows=rows,
        hsNames={h: HS_NAMES.get(h, "HS " + h) for h in {x["hs"] for x in files}},
        columns=COLUMNS,
        brands=load_brands(), hybridCodes=HYBRID_CODES,
    )
    OUT.write_text(TEMPLATE.replace("__DATA__", json.dumps(payload, separators=(",", ":"))), encoding="utf-8")
    ok = sum(1 for x in files if x["n"])
    print("Built %s  |  %d files (%d with data, %d empty)  |  %d records" % (OUT.name, len(files), ok, len(files) - ok, len(rows)))


def signature():
    return sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in HERE.glob("*.json"))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Comtrade Data Viewer</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
:root{--bg:#F4F9FC;--card:#fff;--ink:#072233;--mut:#527084;--deep:#086288;--steel:#4D8DBA;--ice:#97D7FF;--bad:#B3261E;--line:rgba(8,98,136,.14)}
@media(prefers-color-scheme:dark){:root{--bg:#07151e;--card:#0d2230;--ink:#e6f1f7;--mut:#8fb0c2;--deep:#5cb8e0;--steel:#4D8DBA;--ice:#97D7FF;--bad:#ff8a80;--line:rgba(151,215,255,.16)}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px}
h1{margin:0;font-size:24px}h2{font-size:17px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin-bottom:12px}
.top{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}.kpi b{display:block;font-size:22px;color:var(--deep)}.kpi span{color:var(--mut);font-size:12px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--mut);font-weight:600;position:sticky;top:0;background:var(--card);cursor:pointer}td.n,th.n{text-align:right}
.scroll{overflow:auto;max-height:420px}
.cell{display:inline-block;min-width:34px;text-align:center;border-radius:5px;padding:1px 4px;font-size:12px}
.ok{background:rgba(77,141,186,.22)}.empty{background:rgba(179,38,30,.18);color:var(--bad)}.none{color:var(--mut)}
select,input{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font:inherit}
.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.pill{display:inline-block;background:rgba(77,141,186,.18);border-radius:99px;padding:1px 8px;font-size:12px}
.new{background:#2e7d32;color:#fff}.warn{color:var(--bad)}
code{background:rgba(77,141,186,.15);padding:0 4px;border-radius:4px}
.jump{position:sticky;top:0;z-index:5;display:flex;gap:6px;flex-wrap:wrap;background:var(--bg);padding:8px 0;margin-bottom:8px}.jump button{background:var(--card);border:1px solid var(--line);border-radius:99px;padding:5px 14px;color:var(--deep);font:inherit;font-size:13px;cursor:pointer}.jump button.on{background:var(--deep);color:#fff;border-color:var(--deep)}.bgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:12px 0}
.bc{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px;cursor:pointer;text-align:center;font:inherit;color:var(--ink)}
.bc:hover,.bc.on{border-color:var(--deep);box-shadow:0 0 0 2px rgba(8,98,136,.2)}
.logo{width:64px;height:64px;margin:0 auto 6px;border-radius:12px;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden;border:1px solid var(--line)}
.logo img,.logo svg{max-width:46px;max-height:46px}.logo.big{width:84px;height:84px;margin:0}.logo.big img,.logo.big svg{max-width:62px;max-height:62px}
.badge{font-weight:800;font-size:12px;color:#fff;width:100%;height:100%;display:flex;align-items:center;justify-content:center;text-align:center;line-height:1.1;padding:3px;white-space:nowrap}
.mix{display:flex;height:6px;border-radius:3px;overflow:hidden;margin-top:6px;background:var(--line)}
.bhead{display:flex;gap:16px;align-items:center;margin:8px 0 12px;flex-wrap:wrap}
.note{background:rgba(77,141,186,.12);border-left:3px solid var(--steel);padding:8px 12px;border-radius:6px;font-size:13px;margin:10px 0}
.card.hid{display:none}.grid2{display:block!important}html{scroll-behavior:smooth}.card{scroll-margin-top:52px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:800px){.grid2{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<div class="top"><div><h1>UN Comtrade &mdash; Sri Lanka trade data</h1>
<div class="sub">Reporter: Sri Lanka (144) &middot; HS annual data, US$ &middot; built <span id="built"></span></div></div>
<label class="sub"><input type="checkbox" id="auto"> auto-reload page every 15 s</label></div>
<div class="kpis" id="kpis"></div>
<nav class="jump" id="tabs"><button data-t="s1">Contents</button><button data-t="s8">Brands</button><button data-t="s2">Trade over time</button><button data-t="s3">Partners</button><button data-t="s4">Products</button><button data-t="s5">Records</button><button data-t="s6">Files &amp; quality</button><button data-t="s7">Columns</button></nav>

<div class="card" id="s1"><h2>1. What is in this folder</h2>
<div class="sub">One JSON per product (HS code) &times; flow (import/export) &times; year. Cell = number of partner rows returned. <span class="cell empty">0</span> = file exists but the API returned nothing. A dash = never downloaded.</div>
<div class="bar"><label>Flow <select id="mflow"><option>Import</option><option>Export</option></select></label></div>
<div class="scroll" style="max-height:none"><table id="matrix"></table></div></div>

<div class="card" id="s8"><h2>Vehicle brands &rarr; Comtrade</h2>
<div class="sub">Comtrade has <b>no brand field</b>. Each brand is linked to the HS code that matches its models (EV, hybrid, ICE car, pickup/van, bus) and to the country it is mainly sourced from, then we show what Sri Lanka imported <b>from that country</b> under that code. It is a country-level proxy for the brand, not the brand's own sales.</div>
<div id="brandGrid" class="bgrid"></div><div id="brandDetail"></div></div>
<div class="card" id="s2"><h2>2. Trade value over time</h2>
<div class="sub">Uses the <b>World</b> total row (partner 0) so partners are never double counted.</div>
<div class="bar"><label>Product <select id="hsSel"></select></label></div><div id="tsChart" style="height:340px"></div></div>

<div class="grid2">
<div class="card" id="s3"><h2>3. Top partners</h2><div class="sub">Top 10 partners by value for the chosen product, flow and year.</div>
<div class="bar"><select id="hsSel2"></select><select id="pFlow"><option>Import</option><option>Export</option></select><select id="pYear"></select></div>
<div id="partnerChart" style="height:360px"></div></div>
<div class="card" id="s4"><h2>4. Products collected</h2><div class="sub">HS code meaning, years with data, latest value.</div><div class="scroll"><table id="hsTable"></table></div></div></div>

<div class="card" id="s5"><h2>5. Browse the records</h2>
<div class="bar"><input id="q" placeholder="search partner / HS / year..."><span class="sub" id="rcount"></span></div>
<div class="scroll" style="max-height:480px"><table id="rec"></table></div></div>

<div class="card" id="s6"><h2>6. Files &amp; data quality</h2><div id="quality"></div><div class="scroll" style="margin-top:10px"><table id="files"></table></div></div>

<div class="card" id="s7"><h2>7. What the columns mean</h2><table id="cols"></table></div>
<div class="sub">To refresh: add new JSON files here and run <code>python build_comtrade_viewer.py</code> (or leave <code>--watch</code> running). Files modified in the last 24 h are tagged <span class="pill new">new</span>.</div>
</div>
<script>
const D=__DATA__;const $=s=>document.querySelector(s);
const fmt=(v,d=0)=>v==null?'–':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
const usd=v=>v==null?'–':v>=1e9?'$'+(v/1e9).toFixed(2)+'B':v>=1e6?'$'+(v/1e6).toFixed(1)+'M':v>=1e3?'$'+(v/1e3).toFixed(0)+'K':'$'+v.toFixed(0);
const hsName=h=>D.hsNames[h]||('HS '+h);
const rows=D.rows.map(r=>({y:r[0],f:r[1],hs:r[2],pc:r[3],p:r[4],q:r[5],qu:r[6],w:r[7],v:r[8],est:r[9]}));
const hsList=[...new Set(D.files.map(f=>f.hs))].sort((a,b)=>a.length-b.length||a.localeCompare(b));
const years=[...new Set(D.files.map(f=>f.year))].sort();
$('#built').textContent=D.built.replace('T',' ');
const withData=D.files.filter(f=>f.n>0);
const yrsData=[...new Set(withData.map(f=>f.year))].sort();
const emptyF=D.files.filter(f=>f.n===0);
const recent=D.files.filter(f=>Date.now()-new Date(f.modified)<864e5);
$('#kpis').innerHTML=[[D.files.length,'files'],[hsList.length,'HS products'],[yrsData.length?yrsData[0]+'–'+yrsData[yrsData.length-1]:'–','years with data'],[fmt(rows.length),'records'],[emptyF.length,'empty files'],[new Set(rows.map(r=>r.pc)).size-1,'partner countries']].map(k=>`<div class="kpi"><b>${k[0]}</b><span>${k[1]}</span></div>`).join('');
const fkey=(h,f,y)=>h+'|'+f+'|'+y;const fmap={};D.files.forEach(f=>fmap[fkey(f.hs,f.flow,f.year)]=f);
function matrix(){const fl=$('#mflow').value;let h='<tr><th>HS</th><th>Product</th>'+years.map(y=>`<th class="n">${y}</th>`).join('')+'</tr>';
 hsList.forEach(c=>{h+=`<tr><td>${c}</td><td>${hsName(c)}</td>`+years.map(y=>{const f=fmap[fkey(c,fl,y)];return `<td class="n">${f?`<span class="cell ${f.n?'ok':'empty'}">${f.n}</span>`:'<span class="none">–</span>'}</td>`}).join('')+'</tr>'});$('#matrix').innerHTML=h}
$('#mflow').onchange=matrix;matrix();
const worldVal=(hs,fl,y)=>{const r=rows.find(r=>r.hs===hs&&r.f===fl&&r.y===y&&r.pc===0);return r?r.v:null};
$('#hsSel').innerHTML=hsList.map(h=>`<option value="${h}">${h} – ${hsName(h)}</option>`).join('');
function ts(){const h=$('#hsSel').value;const t=['Import','Export'].map((fl,i)=>({x:years,y:years.map(y=>worldVal(h,fl,y)),name:fl,type:'bar',marker:{color:i?'#97D7FF':'#086288'}}));
 Plotly.newPlot('tsChart',t,{barmode:'group',margin:{t:10,l:60,r:10,b:40},yaxis:{title:'US$',tickformat:'.2s'},xaxis:{type:'category'},legend:{orientation:'h',y:1.12},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:getComputedStyle(document.body).color}},{displayModeBar:false,responsive:true});}
$('#hsSel2').innerHTML=$('#hsSel').innerHTML;
$('#hsSel').onchange=()=>{$('#hsSel2').value=$('#hsSel').value;ts();partners()};
$('#hsSel2').onchange=()=>{$('#hsSel').value=$('#hsSel2').value;ts();partners()};ts();
$('#pYear').innerHTML=yrsData.slice().reverse().map(y=>`<option>${y}</option>`).join('');
function partners(){const h=$('#hsSel').value,fl=$('#pFlow').value,y=+$('#pYear').value;
 const r=rows.filter(r=>r.hs===h&&r.f===fl&&r.y===y&&r.pc!==0&&r.v>0).sort((a,b)=>b.v-a.v);const top=r.slice(0,10).reverse();
 if(!top.length){$('#partnerChart').innerHTML='<div class="sub">No partner rows for this selection.</div>';return}
 Plotly.newPlot('partnerChart',[{type:'bar',orientation:'h',x:top.map(t=>t.v),y:top.map(t=>t.p),marker:{color:'#4D8DBA'},text:top.map(t=>usd(t.v)),textposition:'outside',cliponaxis:false,hovertemplate:'%{y}: %{x:,.0f} US$<extra></extra>'}],
 {margin:{t:10,l:130,r:90,b:30},xaxis:{tickformat:'.2s'},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:getComputedStyle(document.body).color}},{displayModeBar:false,responsive:true});}
$('#pFlow').onchange=partners;$('#pYear').onchange=partners;partners();
$('#hsTable').innerHTML='<tr><th>HS</th><th>Product</th><th>Imports yrs</th><th>Exports yrs</th><th class="n">Latest world value</th></tr>'+hsList.map(c=>{
 const yr=fl=>D.files.filter(f=>f.hs===c&&f.flow===fl&&f.n>0).map(f=>f.year).sort();const iy=yr('Import'),ey=yr('Export');
 const last=rows.filter(r=>r.hs===c&&r.pc===0).sort((a,b)=>b.y-a.y)[0];
 return `<tr><td>${c}</td><td>${hsName(c)}</td><td>${iy.length?iy[0]+'–'+iy[iy.length-1]+' ('+iy.length+')':'–'}</td><td>${ey.length?ey[0]+'–'+ey[ey.length-1]+' ('+ey.length+')':'–'}</td><td class="n">${last?usd(last.v)+' ('+last.f[0]+' '+last.y+')':'–'}</td></tr>`}).join('');
let sortK='y',sortD=-1;
function rec(){const q=$('#q').value.toLowerCase();let r=rows.filter(r=>!q||(r.p+' '+r.hs+' '+hsName(r.hs)+' '+r.y+' '+r.f).toLowerCase().includes(q));
 r.sort((a,b)=>(a[sortK]>b[sortK]?1:a[sortK]<b[sortK]?-1:0)*sortD);$('#rcount').textContent=fmt(r.length)+' records (showing first 500)';
 const cols=[['y','Year'],['f','Flow'],['hs','HS'],['p','Partner'],['q','Qty'],['w','Net kg'],['v','Value US$']];
 $('#rec').innerHTML='<tr>'+cols.map(c=>`<th data-k="${c[0]}" class="${'qwv'.includes(c[0])?'n':''}">${c[1]}</th>`).join('')+'</tr>'+r.slice(0,500).map(x=>`<tr><td>${x.y}</td><td>${x.f}</td><td title="${hsName(x.hs)}">${x.hs}</td><td>${x.p}</td><td class="n">${fmt(x.q,1)}</td><td class="n">${fmt(x.w,0)}</td><td class="n">${fmt(x.v,0)}</td></tr>`).join('');
 document.querySelectorAll('#rec th').forEach(t=>t.onclick=()=>{sortD=sortK===t.dataset.k?-sortD:-1;sortK=t.dataset.k;rec()})}
$('#q').oninput=rec;rec();
const emptyYears=[...new Set(emptyF.map(f=>f.year))];
const allEmptyYears=years.filter(y=>D.files.filter(f=>f.year===y).every(f=>f.n===0));
const noQty=rows.filter(r=>r.pc===0&&(r.q==null||r.q===0)).length;
$('#quality').innerHTML=`<ul><li><b>${emptyF.length}</b> of ${D.files.length} files are empty${allEmptyYears.length?` &mdash; <span class="warn">every file for ${allEmptyYears.join(', ')} is empty</span> (the API returned nothing for that year, so charts show gaps).`:'.'}</li>
<li>World-total rows with no quantity: <b>${noQty}</b>. Quantity units differ by product, so don't add quantities across products.</li>
<li>Estimated quantities/weights: <b>${rows.filter(r=>r.est).length}</b> rows flagged <code>isQtyEstimated</code>.</li>
<li>Partner rows are for one partner each; the <b>World</b> row is the total. Never sum World together with partners.</li></ul>`;
$('#files').innerHTML='<tr><th>File</th><th>Product</th><th>Flow</th><th>Year</th><th class="n">Rows</th><th class="n">KB</th><th>Status</th><th>Modified</th></tr>'+D.files.slice().sort((a,b)=>new Date(b.modified)-new Date(a.modified)).map(f=>`<tr><td>${f.file}</td><td>${hsName(f.hs)}</td><td>${f.flow}</td><td>${f.year}</td><td class="n">${f.n}</td><td class="n">${f.kb??''}</td><td class="${f.n?'':'warn'}">${f.status}</td><td>${f.modified.replace('T',' ')} ${recent.includes(f)?'<span class="pill new">new</span>':''}</td></tr>`).join('');
$('#cols').innerHTML='<tr><th>Field</th><th>Meaning</th></tr>'+D.columns.map(c=>`<tr><td><code>${c[0]}</code></td><td style="white-space:normal">${c[1]}</td></tr>`).join('');


// ---------------- Brands tab ----------------
const SVGS={byd:'<svg viewBox="0 0 120 46"><text x="60" y="33" text-anchor="middle" font-family="Arial" font-weight="900" font-size="31" letter-spacing="5" fill="#086288">BYD</text><rect x="14" y="39" width="92" height="3.5" rx="2" fill="#4D8DBA"/></svg>',
 mercedes:'<svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="27" fill="none" stroke="#111827" stroke-width="3.5"/><polygon points="32,7 35,30 55,44 32,35 9,44 29,30" fill="#111827"/></svg>'};
const CNAME={156:'China',392:'Japan',699:'India',276:'Germany',764:'Thailand'};
const BCOL=['#086288','#4D8DBA','#2E7D6B','#7A5195','#B5651D','#C0392B','#34495E','#0E7490'];
const hsCodes=g=>g==='HYBRID'?D.hybridCodes:[g];
const hsLabel=g=>g==='HYBRID'?'Hybrid cars (870340/50/60/70 combined)':g==='8703'?'8703 – all passenger cars (ICE cannot be separated; includes EV & hybrid)':g+' – '+hsName(g);
const colorOf=n=>BCOL[[...n].reduce((a,c)=>a+c.charCodeAt(0),0)%BCOL.length];
let lgN=0;
function logoHTML(b,big){const n=b.name;const cls='logo'+(big?' big':'');const id='lg'+(lgN++);
 if(b.logo.svg)return `<div class="${cls}">${SVGS[b.logo.svg]}</div>`;
 const chain=['brand_logos/'+n+'.svg','brand_logos/'+n+'.png'];if(b.logo.slug)chain.push('https://cdn.simpleicons.org/'+b.logo.slug+'/'+b.logo.color);
 setTimeout(()=>{const box=document.getElementById(id);if(!box)return;let i=0;const img=new Image();img.alt=n;
  img.onload=()=>{box.innerHTML='';box.appendChild(img)};img.onerror=()=>{i++;if(i<chain.length)img.src=chain[i]};img.src=chain[0]},0);
 return `<div class="${cls}" id="${id}"><div class="badge" style="background:${colorOf(n)};font-size:${n.length>7?9:n.length>5?11:13}px">${n}</div></div>`}
const originVal=(g,pcs,y,fl)=>{let t=0,any=false;rows.forEach(r=>{if(r.y===y&&r.f===fl&&r.pc!==0&&pcs.includes(r.pc)&&hsCodes(g).includes(r.hs)){t+=r.v||0;any=true}});return any?t:null};
const worldTot=(g,y,fl)=>{let t=0,any=false;rows.forEach(r=>{if(r.y===y&&r.f===fl&&r.pc===0&&hsCodes(g).includes(r.hs)){t+=r.v||0;any=true}});return any?t:null};
function brandGrid(){$('#brandGrid').innerHTML=D.brands.map((b,i)=>{const c={EV:0,Hybrid:0,ICE:0};b.models.forEach(m=>c[m[1]]=(c[m[1]]||0)+1);const n=b.models.length;
 return `<button class="bc" data-i="${i}">${logoHTML(b)}<b>${b.name}</b><div class="sub" style="margin:0">${n} model${n>1?'s':''} · ${b.origin.map(o=>CNAME[o]).join(' / ')||'origin n/a'}</div>
 <div class="mix" title="ICE / Hybrid / EV"><i style="width:${c.ICE/n*100}%;background:#086288"></i><i style="width:${c.Hybrid/n*100}%;background:#4D8DBA"></i><i style="width:${c.EV/n*100}%;background:#97D7FF"></i></div></button>`}).join('');
 document.querySelectorAll('.bc').forEach(el=>el.onclick=()=>brandDetail(+el.dataset.i))}
function brandDetail(i){const b=D.brands[i];document.querySelectorAll('.bc').forEach((e,k)=>e.classList.toggle('on',k===i));
 const groups=[...new Set(b.models.map(m=>m[4]))];const cnt=g=>b.models.filter(m=>m[4]===g).length;
 const yrs=years.filter(y=>yrsData.includes(y));const orig=b.origin;
 let h=`<div class="bhead">${logoHTML(b,true)}<div><h2 style="margin:0">${b.name}</h2><div class="sub" style="margin:0">${b.models.length} models in the Sri Lanka master list · distributor: ${b.distributors.join(', ')}<br>Assumed source: ${orig.map(o=>CNAME[o]).join(', ')||'unknown'} (editable in <code>BRAND_ORIGIN</code>)</div></div></div>`;
 h+=`<div class="note"><b>How to read:</b> Comtrade only knows country and product code. The numbers below are <u>everything</u> Sri Lanka imported from ${orig.map(o=>CNAME[o]).join(' / ')} under the matching code, from all makes, not only ${b.name}. Use them for context: is the brand's source country a big supplier of that product?</div>`;
 h+='<div class="scroll" style="max-height:none"><table><tr><th>Product code matched</th><th class="n">Models</th><th>Source</th>'+yrs.map(y=>`<th class="n">${y}</th>`).join('')+'<th class="n">Share of SL imports (latest)</th></tr>';
 groups.forEach(g=>{orig.forEach((o,k)=>{const vals=yrs.map(y=>originVal(g,[o],y,'Import'));let sh='–';for(let j=yrs.length-1;j>=0;j--){const w=worldTot(g,yrs[j],'Import');if(vals[j]!=null&&w){sh=(vals[j]/w*100).toFixed(1)+'% ('+yrs[j]+')';break}}
  h+=`<tr>${k===0?`<td rowspan="${orig.length}" style="white-space:normal;max-width:260px">${hsLabel(g)}</td><td class="n" rowspan="${orig.length}">${cnt(g)}</td>`:''}<td>${CNAME[o]}</td>${vals.map(v=>`<td class="n">${v==null?'–':usd(v)}</td>`).join('')}<td class="n">${sh}</td></tr>`})});
 h+='</table></div>';
 h+=`<div class="bar" style="margin-top:12px"><label>Chart product <select id="bg">${groups.map(g=>`<option value="${g}">${hsLabel(g)}</option>`).join('')}</select></label></div><div id="brandChart" style="height:300px"></div>`;
 h+=`<h2 style="margin-top:14px">Models</h2><div class="scroll"><table><tr><th>Model</th><th>Powertrain</th><th>Body</th><th class="n">Price (LKR M, incl. VAT)</th><th>Matched code</th></tr>${b.models.map(m=>`<tr><td>${m[0]}</td><td>${m[1]}</td><td>${m[2]}</td><td class="n">${m[3]==null?'TBA':m[3].toFixed(2)}</td><td>${m[4]==='HYBRID'?'hybrid group':m[4]}</td></tr>`).join('')}</table></div>`;
 $('#brandDetail').innerHTML=h;
 const draw=()=>{const g=$('#bg').value;const tr=orig.map((o,k)=>({x:yrs,y:yrs.map(y=>originVal(g,[o],y,'Import')),name:CNAME[o],type:'bar',marker:{color:BCOL[k]}}));
  tr.push({x:yrs,y:yrs.map(y=>worldTot(g,y,'Import')),name:'All countries',type:'scatter',mode:'lines+markers',line:{color:'#888',dash:'dot'}});
  Plotly.newPlot('brandChart',tr,{barmode:'group',margin:{t:10,l:60,r:10,b:40},yaxis:{title:'US$ imported',tickformat:'.2s'},xaxis:{type:'category'},legend:{orientation:'h',y:1.15},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:getComputedStyle(document.body).color}},{displayModeBar:false,responsive:true})};
 $('#bg').onchange=draw;draw()}
brandGrid();if(D.brands.length)brandDetail(0);
function showTab(t){document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));
 document.querySelectorAll('.card[id^=s]').forEach(c=>c.classList.toggle('hid',c.id!==t));
 try{localStorage.setItem('cmtTab',t)}catch(e){}history.replaceState(null,'','#'+t);
 setTimeout(()=>document.querySelectorAll('.js-plotly-plot').forEach(g=>Plotly.Plots.resize(g)),30)}
document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>showTab(b.dataset.t));
let t0='s1';try{t0=location.hash.slice(1)||localStorage.getItem('cmtTab')||'s1'}catch(e){}
showTab(/^s[1-8]$/.test(t0)?t0:'s1');
let timer;try{$('#auto').checked=localStorage.getItem('cmtAuto')==='1'}catch(e){}
function setAuto(){clearTimeout(timer);try{localStorage.setItem('cmtAuto',$('#auto').checked?'1':'0')}catch(e){}if($('#auto').checked)timer=setTimeout(()=>location.reload(),15000)}
$('#auto').onchange=setAuto;setAuto();
</script></body></html>
"""

if __name__ == "__main__":
    build()
    if "--watch" in sys.argv:
        print("Watching %s for changes (Ctrl+C to stop)..." % HERE)
        last = signature()
        try:
            while True:
                time.sleep(3)
                cur = signature()
                if cur != last:
                    last = cur
                    build()
        except KeyboardInterrupt:
            pass

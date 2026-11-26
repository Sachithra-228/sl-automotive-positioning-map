"""Build data_praveen/00_sketch_overview.html: simple hand-drawn style charts of the data we hold.

Reads the CSVs in data/processed and data/raw/comtrade, so re-running after new data arrives updates the page.
    python data_praveen/scripts/20_build_sketch_overview.py
Needs: pandas, matplotlib.
"""
import base64, io, warnings
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parents[1]
P = HERE / "data" / "processed"
OUT = HERE / "00_sketch_overview.html"
REPO = HERE.parent
INK, BLUE, LIGHT, RED, GREEN = "#1d2b36", "#2f6f9f", "#9cc9e8", "#c0392b", "#3b8a5a"
charts = []


def fig_to_b64(fig):
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="#fffdf7"); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def add(title, caption, source, draw, size=(7.2, 4.2)):
    with plt.xkcd(scale=0.8, length=100, randomness=2):
        fig, ax = plt.subplots(figsize=size)
        fig.patch.set_facecolor("#fffdf7"); ax.set_facecolor("#fffdf7")
        draw(ax)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout()
        charts.append(dict(title=title, caption=caption, source=source, img=fig_to_b64(fig)))


def label_bars(ax, bars, fmt="{:,.0f}", dy=0):
    for b in bars:
        h = b.get_height()
        if h:
            ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h), ha="center", va="bottom", fontsize=8, xytext=(0, 2 + dy), textcoords="offset points")


# 1 ---- monthly total registrations (JB Securities series, press) ----
m = pd.read_csv(P / "registrations_monthly_press_2025_2026.csv")
t = m[(m.metric == "Total registrations") & (m.period.str.match(r"^\d{4}-\d{2}$")) & (m.source_org.str.startswith("JB Securities"))]
t = t.sort_values("period").drop_duplicates("period", keep="last")
t = t[t.period >= "2025-11"]
# JB's May figure is the revised 62,776
def d1(ax):
    bars = ax.bar(t.period.str[2:], t.value, color=BLUE, edgecolor=INK)
    label_bars(ax, bars)
    ax.set_title("Monthly vehicle registrations (all classes)"); ax.set_ylabel("units"); ax.tick_params(axis="x", rotation=45)
    ax.annotate("May peak", xy=(list(t.period).index("2026-05"), 62776), xytext=(1, 66000), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.set_ylim(0, 72000)
add("1. Registrations per month", "Registrations rose from 43.8K (Nov 2025) to a peak of 62.8K in May 2026, then eased. Feb 2026 is missing: no article gave the JB Securities figure.",
    "registrations_monthly_press_2025_2026.csv (JB Securities via Daily FT / Daily Mirror)", d1)

# 2 ---- brand-new cars: BYD vs others, May-Jul 2026 ----
b = pd.read_csv(P / "registrations_by_brand_press_2025_2026.csv")
bn0 = b[(b.segment == "Brand-new cars") & b.units.notna() & b.period.isin(["2026-05", "2026-06", "2026-07"])]
bn = (bn0.groupby(["period", "brand"]).apply(lambda g: g[g.model.isna()].units.sum() if g.model.isna().any() else g.units.sum())
      .rename("units").reset_index())
top = bn.groupby("brand").units.sum().sort_values(ascending=False).head(5).index.tolist()
def d2(ax):
    months = ["2026-05", "2026-06", "2026-07"]; w = 0.16
    for i, br in enumerate(top):
        vals = [bn[(bn.brand == br) & (bn.period == mo)].units.sum() for mo in months]
        bars = ax.bar([x + i * w for x in range(3)], vals, w, label=br, color=[BLUE, LIGHT, GREEN, RED, "#d9a441"][i], edgecolor=INK)
    ax.set_xticks([x + w * 2 for x in range(3)]); ax.set_xticklabels(["May", "Jun", "Jul"]); ax.set_ylabel("registrations")
    ax.set_title("Brand-new cars: who sells"); ax.legend(fontsize=8, frameon=False)
add("2. Brand-new cars by brand", "BAW led in May, then BYD took over (519 in June, 800 in July). Perodua is steady but small. A 0 means the article did not report that brand that month. May is HNB's count, June and July are JB Securities'.",
    "registrations_by_brand_press_2025_2026.csv", d2)

# 3 ---- fleet by type ----
v = pd.read_csv(P / "vehicle_stock_by_type_2019_2023.csv")
def d3(ax):
    kinds = ["Motor cycles", "Three wheelers", "Cars", "Goods vehicles", "Buses"]
    piv = v[v.vehicle_type.isin(kinds)].pivot(index="vehicle_type", columns="year", values="vehicles_in_use").loc[kinds]
    y = range(len(kinds)); ax.barh(list(y), piv[2023] / 1e6, color=BLUE, edgecolor=INK)
    ax.set_yticks(list(y)); ax.set_yticklabels(kinds); ax.invert_yaxis(); ax.set_xlabel("million vehicles in use (2023)")
    for i, k in enumerate(kinds):
        ax.annotate("{:,.2f}M".format(piv.loc[k, 2023] / 1e6), (piv.loc[k, 2023] / 1e6, i), xytext=(4, -3), textcoords="offset points", fontsize=8)
    ax.set_title("Sri Lanka's fleet: mostly two-wheelers")
add("3. The vehicles on the road", "About 8.4 million vehicles in use in 2023. Motorcycles are the biggest group, then three-wheelers; cars are only about 0.9 million.",
    "vehicle_stock_by_type_2019_2023.csv (DCS Table 7.2)", d3)

# 4 ---- new car registrations by fuel 2019-2023 ----
r = pd.read_csv(P / "dmt_new_registrations_by_class_fuel_2019_2023.csv")
def d4(ax):
    c = r[r.vehicle_class == "Motor cars"].groupby(["year", "powertrain"]).registrations.sum().unstack(fill_value=0)
    bottom = None; cols = [("Petrol", BLUE), ("Hybrid", GREEN), ("Diesel", "#d9a441"), ("Electric (BEV)", RED)]
    import numpy as np; bottom = np.zeros(len(c))
    for name, col in cols:
        if name in c:
            ax.bar(c.index.astype(str), c[name], bottom=bottom, label=name, color=col, edgecolor=INK); bottom += c[name].values
    ax.set_title("New motor cars registered per year (import ban years)"); ax.set_ylabel("units"); ax.legend(fontsize=8, frameon=False)
_c = r[(r.vehicle_class == "Motor cars") & r.powertrain.isin(["Petrol", "Hybrid", "Diesel", "Electric (BEV)"])].groupby("year").registrations.sum()
add("4. Car registrations fell off a cliff", "The import suspension shows up: new motor cars drop from about %.0fK (2019) to about %.1fK (2023), and hybrids collapse. 2025's rebound is not in this table (it ends at 2023)." % (_c[2019] / 1000, _c[2023] / 1000),
    "dmt_new_registrations_by_class_fuel_2019_2023.csv (DCS Table 7.3, DMT)", d4)

# 5 ---- company revenue ----
f = pd.read_csv(P / "company_financials.csv")
def d5(ax):
    rev = f[(f.metric == "Revenue") & f.fiscal_year.isin(["2023/24", "2024/25", "2025/26"]) & (f.note != "Company only")]
    piv = rev.pivot_table(index="fiscal_year", columns="company", values="value") / 1000
    w = 0.25
    for i, (co, col) in enumerate(zip(piv.columns, [BLUE, LIGHT, GREEN])):
        bars = ax.bar([x + i * w for x in range(len(piv))], piv[co].fillna(0), w, label=co, color=col, edgecolor=INK)
        label_bars(ax, bars, "{:.0f}")
    ax.set_xticks([x + w for x in range(len(piv))]); ax.set_xticklabels(piv.index); ax.set_ylabel("Rs billion")
    ax.set_title("Listed distributors: revenue"); ax.legend(fontsize=8, frameon=False)
add("5. Distributor revenue", "Group revenue. DIMO more than doubled (43.6 to 103.6) and United Motors grew 4.5x (11.6 to 52.4) since 2023/24. Lanka Ashok Leyland has no 2025/26 figure in our data (shown as 0).",
    "company_financials.csv (audited annual reports)", d5)

# 6 ---- vehicle import bill (CBSL) ----
imp = pd.read_csv(P / "vehicle_imports_cbsl_monthly.csv")
imp = imp[imp.period.str.match(r"^\d{4}-\d{2}$")].sort_values("period")
def d6(ax):
    bars = ax.bar(imp.period.str[2:], imp.vehicle_import_bill_usd_mn, color=[LIGHT if p < "2026" else BLUE for p in imp.period], edgecolor=INK)
    label_bars(ax, bars); ax.set_ylabel("US$ million"); ax.set_title("Vehicle import bill per month"); ax.tick_params(axis="x", rotation=45)
add("6. What vehicle imports cost", "Roughly US$200-310M a month. December 2025 peaked at US$311M; June 2026 was US$182M. Months with no article are simply missing, not zero.",
    "vehicle_imports_cbsl_monthly.csv (CBSL as quoted by press)", d6)

# 7 ---- Comtrade: electric car imports by year (world total) ----
ct = pd.read_csv(P / "comtrade_sl_trade_clean.csv")
def d7(ax):
    for hs, lab, col in [("8703", "All passenger cars (8703)", BLUE), ("870380", "Electric cars (870380)", RED)]:
        s = ct[(ct.hs.astype(str) == hs) & (ct.flow == "Import") & (ct.partner_code == 0)].groupby("year").value_usd.sum() / 1e6
        ax.plot(s.index, s.values, marker="o", label=lab, color=col)
    ax.set_yscale("log"); ax.set_ylabel("US$ million (log scale)"); ax.set_title("Car imports into Sri Lanka (Comtrade)"); ax.legend(fontsize=8, frameon=False)
    ax.annotate("import ban", xy=(2021, 15), xytext=(2019.6, 5), arrowprops=dict(arrowstyle="->"), fontsize=9)
add("7. Car imports (UN Comtrade)", "Log scale (each gridline is 10x). Car imports collapse from about US$650M (2019) during the ban; electric cars go from US$0.5M (2017) to US$9M (2023) and US$37M (2024). 2018 is blank: the API returned nothing for that year.",
    "comtrade_sl_trade_clean.csv, world-total rows", d7)

# 8 ---- models per brand in the master list ----
mm = pd.read_csv(REPO / "data" / "processed" / "master_sl_automotive.csv")
def d8(ax):
    c = mm.groupby(["Brand", "Powertrain"]).size().unstack(fill_value=0)
    c["t"] = c.sum(axis=1); c = c.sort_values("t")
    left = None; import numpy as np; left = np.zeros(len(c))
    for name, col in [("ICE", INK), ("Hybrid", BLUE), ("EV", LIGHT)]:
        if name in c:
            ax.barh(c.index, c[name], left=left, label=name, color=col, edgecolor=INK); left += c[name].values
    ax.set_xlabel("models in the master list"); ax.set_title("Brands in our model list"); ax.legend(fontsize=8, frameon=False, loc="lower right")
add("8. Models per brand (our master list)", "Toyota has the most models but none has a price yet; BYD and Mercedes follow. Chinese EV brands (BYD, BAW, Wuling...) are mostly hybrids and EVs, Toyota and Mercedes are mostly ICE.",
    "data/processed/master_sl_automotive.csv", d8, size=(7.2, 5.2))

# ---- page ----
import datetime
cards = "\n".join(
    '<section><h2>%s</h2><img src="data:image/png;base64,%s" alt="%s"><p>%s</p><small>Data: %s</small></section>' % (c["title"], c["img"], c["title"], c["caption"], c["source"])
    for c in charts)
html = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sri Lanka vehicle data - sketch overview</title>
<style>body{margin:0;background:#fffdf7;color:#1d2b36;font:16px/1.5 'Segoe Print','Comic Sans MS',cursive,sans-serif}
.w{max-width:1100px;margin:0 auto;padding:24px 16px 60px}h1{margin:0 0 4px}.sub{color:#58707f;margin-bottom:20px}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:22px}
section{background:#fff;border:2px solid #1d2b36;border-radius:14px 22px 12px 20px;padding:14px;box-shadow:4px 4px 0 #1d2b36}
h2{margin:0 0 6px;font-size:19px}img{width:100%%;height:auto}p{margin:8px 0 4px;font-size:14px}small{color:#58707f}
@media(max-width:480px){.g{grid-template-columns:1fr}}</style></head><body><div class="w">
<h1>Sri Lanka vehicle data, sketched</h1><div class="sub">Built %s from the CSVs in data_praveen. Re-run <code>scripts/20_build_sketch_overview.py</code> to refresh. Press-sourced numbers are secondary (JB Securities, HNB, CBSL via newspapers).</div>
<div class="g">%s</div></div></body></html>""" % (datetime.datetime.now().strftime("%d %b %Y"), cards)
OUT.write_text(html, encoding="utf-8")
print("wrote", OUT, len(charts), "charts,", round(OUT.stat().st_size / 1024), "KB")

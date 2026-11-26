"""Load Sri Lanka vehicle-registration data compiled by brokerages and reported in the press.

Every number below was read from the article named in SOURCES (snapshots saved under
data/raw/pages/press/ and data/interim/press/). These are SECONDARY sources (JB Securities,
HNB Stockbrokers, CAL Research, CBSL as quoted by newspapers), not the Department of Motor Traffic tables.

Run:  python data_praveen/scripts/10_load_press_registrations.py
Idempotent: rewrites the three processed CSVs and only appends conflict / manifest rows that are not there yet.
"""
import csv, datetime, html, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data"
PROC, RAW, INTERIM = ROOT / "processed", ROOT / "raw", ROOT / "interim"

# key -> (publication, url, organisation whose figures are quoted)
SOURCES = {
    "ft_jul26": ("Daily FT, 31 Aug 2026", "https://www.ft.lk/front-page/Vehicle-registrations-continue-to-slide-in-July/44-796538", "JB Securities"),
    "ft_jun26": ("Daily FT, Jul 2026", "https://www.ft.lk/front-page/Vehicle-registrations-fall-in-June-SUVs-extend-gains-JB-Securities/44-795220", "JB Securities"),
    "ft_jun26_imp": ("Daily FT, Jul 2026", "https://www.ft.lk/front-page/Vehicle-import-bill-falls-27--M-o-M-in-June/44-795481", "CBSL / JB Securities"),
    "ft_may26": ("Daily FT, 11 Jun 2026", "https://www.ft.lk/top-story/Vehicle-registrations-hit-new-high-in-May/26-793134", "HNB Stockbrokers"),
    "ft_apr26": ("Daily FT, May 2026", "https://www.ft.lk/top-story/Vehicle-registrations-fall-sharply-in-April/26-792430", "JB Securities"),
    "dm_mar26": ("Daily Mirror print, Apr 2026", "https://www.dailymirror.lk/print/business-main/March-vehicle-registrations-expand-over-15-as-EV-adoption-accelerates/245-338794", "JB Securities / CBSL"),
    "dm_jan26": ("Daily Mirror print, Feb 2026", "https://www.dailymirror.lk/print/breaking-news/Vehicle-registrations-hit-record-high-in-January/108-333330", "JB Securities"),
    "ft_dec25": ("Daily FT, Jan 2026", "https://www.ft.lk/top-story/Vehicle-registrations-surge-in-December-2025-to-10-year-high/26-787250", "JB Securities / CBSL"),
    "dm_aug25": ("Daily Mirror, Sep 2025", "https://www.dailymirror.lk/breaking-news/BYD-roars-back-as-SLs-vehicle-market-sees-tepid-growth/108-319630", "CAL Research"),
    "dm_ev25": ("Daily Mirror, Jul-Aug 2025", "https://www.dailymirror.lk/breaking-news/EV-surge-reshapes-Sri-Lankas-auto-market/108-314002", "HNB Stockbrokers (Jul 2025 report)"),
    "ft_byd": ("Daily FT, Jan 2026", "https://www.ft.lk/motor/BYD-leading-SL-s-brand-new-vehicle-segment-moves-to-strengthen-network-after-sales/55-787609", "BYD / John Keells CG Auto (company statement)"),
    "chamber": ("Ceylon Chamber of Commerce, Aug 2026", "https://www.chamber.lk/ceylon-chambers-motor-vehicle-industry-report-returns-after-six-years-as-sri-lankas-vehicle-market-enters-a-new-phase/", "Ceylon Chamber (report is paid; brand tables NOT public)"),
}
# local snapshot name -> source key (fetched 2026-11-26)
SNAPSHOTS = {"3fafbe": "ft_jul26", "p1": "ft_jun26", "p3": "ft_jun26_imp", "18a063": "ft_may26", "p2": "ft_apr26", "p5": "dm_mar26",
             "p4": "dm_jan26", "9e2688": "ft_dec25", "p6": "dm_aug25", "p7": "dm_ev25", "2f76b9": "ft_byd", "183d93": "chamber"}

# ---- 1. monthly market totals: (period, metric, segment, value, unit, source_key, note) ----
TOTALS = [
    ("2025-11", "Total registrations", "All", 43810, "units", "ft_dec25", ""),
    ("2025-12", "Total registrations", "All", 48525, "units", "ft_dec25", "Highest monthly level in a decade. HNB quotes ~47,900 for Dec (see source_conflicts)."),
    ("2026-01", "Total registrations", "All", 55365, "units", "dm_jan26", "HNB rounds to 54,100"),
    ("2026-03", "Total registrations", "All", 59734, "units", "dm_mar26", "+15.6% m/m"),
    ("2026-04", "Total registrations", "All", 51156, "units", "ft_apr26", "HNB rounds to 50,500"),
    ("2026-05", "Total registrations", "All", 60444, "units", "ft_may26", "HNB figure. JB Securities later reports 62,776 for May."),
    ("2026-05", "Total registrations", "All", 62776, "units", "ft_jun26", "JB Securities figure (revised)."),
    ("2026-06", "Total registrations", "All", 58151, "units", "ft_jun26", ""),
    ("2026-07", "Total registrations", "All", 53221, "units", "ft_jul26", "-8.5% m/m, 15.2% below May peak"),
    ("2025-07", "Total registrations", "All", 37543, "units", "dm_aug25", ""),
    ("2025-08", "Total registrations", "All", 38240, "units", "dm_aug25", ""),
    ("2026-03", "Motor car registrations", "Cars", 4856, "units", "dm_mar26", "new + pre-owned"),
    ("2026-04", "Motor car registrations", "Cars", 3238, "units", "ft_apr26", ""),
    ("2026-05", "Motor car registrations", "Cars", 4738, "units", "ft_jun26", ""),
    ("2026-06", "Motor car registrations", "Cars", 3929, "units", "ft_jun26", ""),
    ("2026-07", "Motor car registrations", "Cars", 3654, "units", "ft_jul26", ""),
    ("2025-12", "Motor car registrations", "Cars", 5007, "units", "dm_jan26", ""),
    ("2026-01", "Motor car registrations", "Cars", 4648, "units", "dm_jan26", ""),
    ("2025-07", "Motor car registrations", "Cars", 6745, "units", "dm_aug25", ""),
    ("2025-08", "Motor car registrations", "Cars", 6475, "units", "dm_aug25", ""),
    ("2025-12", "Brand-new car registrations", "Cars", 1150, "units", "dm_jan26", ""),
    ("2026-01", "Brand-new car registrations", "Cars", 556, "units", "dm_jan26", ""),
    ("2026-03", "Brand-new car registrations", "Cars", 1432, "units", "ft_apr26", ""),
    ("2026-04", "Brand-new car registrations", "Cars", 467, "units", "ft_apr26", ""),
    ("2026-05", "Brand-new car registrations", "Cars", 1199, "units", "ft_jun26", "JB Securities. HNB reports 1,110 for May."),
    ("2026-05", "Brand-new car registrations", "Cars", 1110, "units", "ft_may26", "HNB Stockbrokers figure."),
    ("2026-06", "Brand-new car registrations", "Cars", 998, "units", "ft_jun26", ""),
    ("2026-07", "Brand-new car registrations", "Cars", 1062, "units", "ft_jul26", "Financing share 42.8%"),
    ("2026-06", "Pre-owned car registrations", "Cars", 2931, "units", "ft_jun26", ""),
    ("2026-07", "Pre-owned car registrations", "Cars", 2592, "units", "ft_jul26", ""),
    ("2026-01", "Pre-owned car registrations", "Cars", 4092, "units", "dm_jan26", ""),
    ("2026-03", "SUV and crossover registrations", "SUV", 5841, "units", "ft_apr26", ""),
    ("2026-04", "SUV and crossover registrations", "SUV", 4853, "units", "ft_apr26", ""),
    ("2026-06", "SUV and crossover registrations", "SUV", 5933, "units", "ft_jun26_imp", ""),
    ("2026-07", "SUV and crossover registrations", "SUV", 4439, "units", "ft_jul26", ""),
    ("2026-04", "Hybrid registrations", "Hybrid", 2316, "units", "ft_apr26", ""),
    ("2026-03", "Hybrid registrations", "Hybrid", 2512, "units", "ft_apr26", ""),
    ("2026-06", "Hybrid registrations", "Hybrid", 3023, "units", "ft_jul26", ""),
    ("2026-07", "Hybrid registrations", "Hybrid", 2288, "units", "ft_jul26", ""),
    ("2026-03", "EV registrations (all classes)", "EV", 8805, "units", "ft_apr26", ""),
    ("2026-04", "EV registrations (all classes)", "EV", 8098, "units", "ft_apr26", "of which electric two-wheelers 7,452"),
    ("2026-06", "EV registrations (all classes)", "EV", 7745, "units", "ft_jul26", ""),
    ("2026-07", "EV registrations (all classes)", "EV", 7170, "units", "ft_jul26", "of which electric two-wheelers 5,544; EV motor cars 992"),
    ("2026-01", "Two-wheeler registrations", "2W", 35533, "units", "dm_jan26", "motorcycles and scooters; electric 2,976"),
    ("2026-03", "Two-wheeler registrations", "2W", 41121, "units", "dm_mar26", ""),
    ("2026-04", "Two-wheeler registrations", "2W", 38631, "units", "ft_apr26", ""),
    ("2026-05", "Two-wheeler registrations", "2W", 43166, "units", "ft_may26", ""),
    ("2026-06", "Two-wheeler registrations", "2W", 40007, "units", "ft_jul26", ""),
    ("2026-07", "Two-wheeler registrations", "2W", 38216, "units", "ft_jul26", ""),
    ("2026-03", "Three-wheeler registrations", "3W", 4031, "units", "dm_mar26", ""),
    ("2026-04", "Three-wheeler registrations", "3W", 1355, "units", "ft_apr26", ""),
    ("2026-06", "Three-wheeler registrations", "3W", 4962, "units", "ft_jul26", ""),
    ("2026-07", "Three-wheeler registrations", "3W", 3741, "units", "ft_jul26", ""),
    ("2026-07", "Locally assembled registrations", "All", 5330, "units", "ft_jul26", "of which two-wheelers 4,691"),
    ("2026-06", "Locally assembled registrations", "All", 5314, "units", "ft_jul26", ""),
    ("2026-07", "Imports by source market: India", "All", 33201, "units", "ft_jul26", "two-wheelers 27,341"),
    ("2026-06", "Imports by source market: India", "All", 36307, "units", "ft_jul26", ""),
    ("2026-07", "Imports by source market: China", "All", 7626, "units", "ft_jul26", ""),
    ("2026-06", "Imports by source market: China", "All", 8165, "units", "ft_jul26", ""),
    ("2026-07", "Imports by source market: Japan", "All", 6050, "units", "ft_jul26", "approximate (\"around 6,050\")"),
    ("2025", "Passenger vehicle registrations (cars+SUVs+vans)", "Passenger", 68323, "units", "ft_dec25", "2015 = 82,489; 2025 is ~50% above 2019"),
    ("2025", "SUV and crossover share of passenger registrations", "SUV", 52, "percent", "ft_dec25", "2019 = 16%, 2015 = 12%"),
    ("2025", "Car share of passenger registrations", "Cars", 42, "percent", "ft_dec25", "2019 = 67%, 2015 = 74%"),
    ("2025", "Registrations by origin: Japan", "All", 62, "percent", "ft_dec25", "2019 = 81%, 2015 = 51%"),
    ("2025", "Registrations by origin: India", "All", 8, "percent", "ft_dec25", "2015 = 51%"),
    ("2025", "Registrations by origin: China", "All", 8, "percent", "ft_dec25", "virtually absent in 2015 and 2019"),
    ("2025", "Vehicle import tax revenue", "All", 905, "Rs billion", "ft_dec25", "Deputy Minister says Rs 904bn; Ceylon Chamber says Rs 896.4bn (see source_conflicts)"),
]

# ---- 2. brand level: (period, segment, brand, model, units, share_pct, basis, source_key, note) ----
B = []
def brand(period, seg, brand_, model, units, share, src, note="", basis="registrations"):
    B.append((period, seg, brand_, model, units, share, basis, src, note))

# July 2026
for br, m, u in [("BYD", "", 800), ("BYD", "Atto 1", 612), ("BYD", "Dolphin Dynamic", 180), ("BAW", "E7", 63), ("Wuling", "", 53), ("Perodua", "", 27)]:
    brand("2026-07", "Brand-new cars", br, m, u, "", "ft_jul26", "total brand-new cars 1,062" if not m and br == "BYD" else "")
for br, m, u in [("Suzuki", "", 835), ("Suzuki", "Wagon R", 649), ("Toyota", "", 745), ("Nissan", "", 439), ("Daihatsu", "", 420)]:
    brand("2026-07", "Pre-owned cars", br, m, u, "", "ft_jul26")
for br, m, u in [("Toyota", "", 1401), ("Toyota", "Raize", 930), ("Toyota", "Urban Cruiser", 294), ("Honda", "", 936), ("Honda", "Vezel", 923), ("BYD", "", 490)]:
    brand("2026-07", "SUV and crossover (new + pre-owned)", br, m, u, "", "ft_jul26")
brand("2026-07", "EV motor cars", "BYD", "", 801, "", "ft_jul26", "of 992 EV motor cars")
brand("2026-07", "All classes", "BYD", "", 1290, "", "ft_jul26", "cars + SUVs; the 'Chinese imports' line")
for br, u in [("Honda", 8510), ("Bajaj", 8096), ("TVS", 6932), ("Yamaha", 4227), ("Hero", 3720)]:
    brand("2026-07", "Two-wheelers", br, "", u, "", "ft_jul26")
# June 2026
for br, m, u in [("BYD", "", 519), ("BYD", "Atto 1", 373), ("BYD", "Dolphin Dynamic", 131), ("Perodua", "", 160), ("Perodua", "Bezza", 82), ("Perodua", "Axia", 78), ("BAW", "E7", 108), ("Kaiyi", "", 56)]:
    brand("2026-06", "Brand-new cars", br, m, u, "", "ft_jun26", "total brand-new cars 998" if not m and br == "BYD" else "")
for br, m, u in [("Suzuki", "", 987), ("Suzuki", "Wagon R", 764), ("Suzuki", "Spacia", 90), ("Suzuki", "Alto", 76), ("Toyota", "", 767), ("Toyota", "Roomy", 382), ("Toyota", "Yaris", 315), ("Nissan", "", 525), ("Nissan", "Dayz", 385), ("Daihatsu", "", 433), ("Daihatsu", "Mira", 342)]:
    brand("2026-06", "Pre-owned cars", br, m, u, "", "ft_jun26")
for br, u in [("Mercedes-Benz", 59), ("Audi", 43), ("BMW", 27), ("Lexus", 12)]:
    brand("2026-06", "Premium passenger (new + pre-owned)", br, "", u, "", "ft_jun26")
# May 2026
for br, u in [("BAW", 519), ("BYD", 436), ("Perodua", 65)]:
    brand("2026-05", "Brand-new cars", br, "", u, "", "ft_may26", "HNB basis: brand-new cars 1,110; EVs = 91% of them")
brand("2026-05", "Brand-new SUVs", "Suzuki", "Fronx", "", 32.6, "ft_may26", "share of 1,606 brand-new SUVs", "market share")
brand("2026-05", "Brand-new SUVs", "BYD", "", "", 20.3, "ft_may26", "share of 1,606 brand-new SUVs", "market share")
# April / March 2026
for br, u in [("Toyota", 1725), ("Honda", 906), ("Suzuki", 688)]:
    brand("2026-04", "SUV and crossover (new + pre-owned)", br, "", u, "", "ft_apr26")
brand("2026-04", "Motor cars", "BYD", "", 29, "", "ft_apr26", "down from 807 in March")
brand("2026-03", "Motor cars", "BYD", "", 807, "", "ft_apr26", "stated in the April article")
for br, u in [("Bajaj", 9924), ("TVS", 8600), ("Honda", 5117)]:
    brand("2026-04", "Two-wheelers", br, "", u, "", "ft_apr26")
brand("2026-01", "Brand-new cars", "BAW", "E7", "", "", "dm_jan26", "BAW led brand-new registrations, almost entirely E7; units not stated", "qualitative")
# 2025
for br, m, u, s in [("BYD", "", 1204, 72), ("BYD", "Atto 3", 677, ""), ("BYD", "Sealion 6", 526, "")]:
    brand("2025-03..2025-05", "Brand-new SUV and crossover", br, m, u, s, "dm_ev25", "HNB Stockbrokers, Mar-May 2025 cumulative")
for br, m, u, s in [("Perodua", "", 352, 60), ("BYD", "", 178, 30), ("BYD", "Dolphin", 78, ""), ("BYD", "Seal", 95, "")]:
    brand("2025-03..2025-05", "Brand-new cars", br, m, u, s, "dm_ev25", "HNB Stockbrokers, Mar-May 2025 cumulative")
for m, u in [("", 1424), ("Atto", 554), ("Sealion", 465), ("Seal", 307)]:
    brand("2025-08", "All classes", "BYD", m, u, "", "dm_aug25", "July 2025 = 790")
brand("2025-08", "Trucks", "Toyota", "", "", 24, "dm_aug25", "of 918 trucks", "market share")
brand("2025-08", "Trucks", "Lanka Ashok Leyland", "", "", 13, "dm_aug25", "of 918 trucks", "market share")
brand("2025-08", "Trucks", "Tata", "", "", 13, "dm_aug25", "of 918 trucks", "market share")
brand("2025-08", "Buses", "Lanka Ashok Leyland", "", "", 22, "dm_aug25", "of 72 buses", "market share")
brand("2025-08", "Three-wheelers", "Bajaj", "", 2286, 92, "dm_aug25", "of 2,497", "registrations")
brand("2025-08", "Two-wheelers", "Bajaj", "", "", 37, "dm_aug25", "", "market share")
brand("2025-08", "Two-wheelers", "TVS", "", "", 25, "dm_aug25", "", "market share")
brand("2025-04..2026-01", "Brand-new vehicles", "BYD", "", "", 37, "ft_byd", "nine months after imports resumed; company statement", "market share")
brand("2025-04..2026-01", "EV (cumulative)", "BYD", "", "", 70, "ft_byd", "'over 70%' of cumulative EV registrations; company statement", "market share")

# ---- 3. CBSL vehicle import bill (US$ million) ----
IMPORTS = [
    ("2025-09", 286, "ft_dec25", "peak month of 2025 until December"), ("2025-10", 261, "ft_dec25", ""), ("2025-11", 281, "ft_dec25", ""),
    ("2025-12", 311, "dm_jan26", "peak"), ("2026-01", 236.4, "dm_mar26", ""), ("2026-02", 204.8, "dm_mar26", "-13.4% m/m"),
    ("2026-06", 182, "ft_jun26_imp", "-27% m/m"),
    ("2025-01..2025-11", 1700, "ft_dec25", "cumulative, approx. (US$1.7bn)"),
    ("2026-H1", 1254, "ft_jun26_imp", "cumulative first half of 2026"), ("2025-H2", 1572, "ft_jun26_imp", "cumulative second half of 2025"),
]

CONFLICTS = [
    ("Total registrations May 2026", "HNB Stockbrokers (Daily FT 11 Jun 2026)", 60444, "units", "First estimate", "Use 62,776 (JB Securities, repeated in June and July reports). Both kept in registrations_monthly_press_2025_2026.csv."),
    ("Total registrations May 2026", "JB Securities (Daily FT, Jul-Aug 2026)", 62776, "units", "Revised / different compiler", "Preferred: quoted consistently by JB Securities in three later articles."),
    ("Brand-new car registrations May 2026", "HNB Stockbrokers", 1110, "units", "Different compiler", "Both kept; JB Securities (1,199) is used for time series because it covers Mar-Jul consistently."),
    ("Brand-new car registrations May 2026", "JB Securities", 1199, "units", "Different compiler", "Preferred for time series."),
    ("Total registrations Dec 2025", "HNB Stockbrokers (rounded)", 47900, "units", "Rounded series in the May 2026 article", "Use 48,525 (JB Securities)."),
    ("Total registrations Dec 2025", "JB Securities", 48525, "units", "", "Preferred."),
    ("Vehicle import tax revenue 2025", "Ceylon Chamber Motor Vehicle Industry Report", 896.4, "Rs billion", "Customs revenue", "Not combined: scope may differ (Customs revenue vs all import taxes)."),
    ("Vehicle import tax revenue 2025", "Deputy Minister / JB Securities (Daily FT)", 904, "Rs billion", "Taxes on vehicle imports", "Not combined: see above."),
]

COLS_T = ["period", "metric", "segment", "value", "unit", "source_org", "publication", "source_type", "url", "note"]
COLS_B = ["period", "segment", "brand", "model", "units", "share_pct", "basis", "source_org", "publication", "source_type", "url", "note"]
COLS_I = ["period", "vehicle_import_bill_usd_mn", "source_org", "publication", "source_type", "url", "note"]


def stype(k):
    return "primary_company_statement" if k == "ft_byd" else "secondary_news"


def write(path, cols, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
    print("wrote", path.relative_to(ROOT.parent), len(rows), "rows")


def src(k):
    pub, url, org = SOURCES[k]
    return org, pub, stype(k), url


def main():
    seen = set(); trows = []
    for p, m, seg, v, u, k, n in TOTALS:
        key = (p, m, v, k)
        assert key not in seen, key; seen.add(key)
        trows.append([p, m, seg, v, u, *src(k)[:2], src(k)[2], src(k)[3], n])
    write(PROC / "registrations_monthly_press_2025_2026.csv", COLS_T, sorted(trows, key=lambda r: (r[1], r[0])))
    brows = [[p, s, b, m, u, sh, bas, *src(k)[:2], src(k)[2], src(k)[3], n] for p, s, b, m, u, sh, bas, k, n in B]
    # brand rows: column order is period, segment, brand, model, units, share_pct, basis, ...
    write(PROC / "registrations_by_brand_press_2025_2026.csv", COLS_B, brows)
    irows = [[p, v, *src(k)[:2], src(k)[2], src(k)[3], n] for p, v, k, n in IMPORTS]
    write(PROC / "vehicle_imports_cbsl_monthly.csv", COLS_I, irows)

    # source conflicts (append once)
    sc = PROC / "source_conflicts.csv"
    existing = sc.read_text(encoding="utf-8-sig")
    with sc.open("a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if not existing.endswith("\n"):
            fh.write("\n")
        added = 0
        for row in CONFLICTS:
            if row[0] in existing and str(row[2]) in existing:
                continue
            w.writerow(row); added += 1
    print("source_conflicts rows added:", added)

    # snapshots: raw html + interim text
    (RAW / "pages" / "press").mkdir(parents=True, exist_ok=True); (INTERIM / "press").mkdir(parents=True, exist_ok=True)
    scratch = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    manifest = RAW / "DOWNLOAD_MANIFEST.csv"; mtxt = manifest.read_text(encoding="utf-8")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if scratch and scratch.exists():
        for name, key in SNAPSHOTS.items():
            f = scratch / (name + ".html")
            if not f.exists():
                continue
            raw = f.read_bytes(); dest = RAW / "pages" / "press" / (key + ".html"); dest.write_bytes(raw)
            s = re.sub(r"(?s)<(script|style|noscript)[^>]*>.*?</\1>", "", raw.decode("utf-8", "ignore"))
            lines = [l.strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", s)).split("\n") if len(l.strip()) > 70 and "function" not in l]
            (INTERIM / "press" / (key + ".txt")).write_text(SOURCES[key][1] + "\n" + "\n".join(lines), encoding="utf-8")
            url = SOURCES[key][1]
            if url not in mtxt:
                with manifest.open("a", encoding="utf-8", newline="") as fh:
                    fh.write("%s,data/raw/pages/press/%s.html,%s,%d\n" % (url, key, now, len(raw)))
    print("done")


if __name__ == "__main__":
    main()

# Sri Lanka Automotive Market — Product Positioning Map

MECE Product Positioning Map (9-Box Scatter Plot) and Strategic Analysis for Sri Lanka's Brand-New Automotive Market — comparing **ICE**, **Hybrid**, and **EV** portfolios across **Budget**, **Mid-Range**, and **Premium** tiers, paired with **The SCALE Pathway** frameworks (Strategy Palette, Innovator's Dilemma, Blue Ocean Strategy Canvas & ERRC Grid, Three Horizons).

---

## Team Assembly Line (5 Members)

| Member | Branch | Role | Ownership |
| :--- | :--- | :--- | :--- |
| **Sachithra** | `docs/sachithra-strategy-and-deck` | Sprint Lead & Deck Owner | MECE Registry (CAL Report), SCALE Frameworks, Final Presentation Deck |
| **Arundathie** | `data/arundathie-legacy-distributors` | Data Lead — Batch A | Legacy Giants (`United Motors`, `DIMO`, `AMW`, `Toyota Lanka`) |
| **Sithumini** | `data/sithumini-new-entrants-ev` | Data Lead — Batch B | New Entrants & EVs (`John Keells/BYD`, `Euro Motors/Jetour`, `Hayleys/Jaecoo`, `Kia`, `Hyundai`, `Micro`) |
| **Thilakshana** | `data/thilakshana-specialty-and-qa` | Data Batch C + QA Auditor | Specialty/Luxury Brands (`Colonial`, `Prestige/BMW`, `Access`, `Carmart`, `Stafford`, `Sathosa`, `Senok`) + VAT Normalization & Master CSV |
| **Praveen** | `feat/praveen-positioning-charts` | Data Science & Viz Lead | Python 9-Box Scatter Plot, Portfolio Mix Chart & Blue Ocean Strategy Canvas |

---

## Repository Structure

```text
├── data/
│   ├── raw/                        # Individual batch CSVs (batch_a_arundathie.csv, batch_b_sithumini.csv, batch_c_thilakshana.csv)
│   └── processed/                  # Audited, VAT-normalized master_sl_automotive.csv
├── scripts/
│   └── plot_positioning_map.py     # Generates 9-Box Scatter Plot, Portfolio Mix & Strategy Canvas
└── outputs/                        # High-res PNG/SVG charts & final presentation deck
```

## Quick Start (for Praveen)

```bash
pip install pandas matplotlib seaborn
python scripts/plot_positioning_map.py
```

By default, if `data/processed/master_sl_automotive.csv` is not yet populated, the script runs on realistic sample data so you can verify the visual layout immediately.

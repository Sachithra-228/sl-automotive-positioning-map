"""
Sri Lanka Brand-New Automotive Market — 9-Box Product Positioning Map & Charts
Author: Sprint Team (Praveen — Data Science & Viz Lead)

Usage:
    python scripts/plot_positioning_map.py

Reads `data/processed/master_sl_automotive.csv` if present; otherwise uses
sample data so the visual pipeline can be verified immediately.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "processed" / "master_sl_automotive.csv"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Price tier cutoffs in LKR Millions (VAT-Inclusive) — adjust after seeing real distribution
BUDGET_MAX = 12.0
MIDRANGE_MAX = 25.0


def load_data() -> pd.DataFrame:
    if DATA_PATH.exists():
        df = pd.read_csv(DATA_PATH)
        print(f"Loaded {len(df)} rows from {DATA_PATH}")
        return df

    print("master_sl_automotive.csv not found — using sample data for layout preview.")
    sample = [
        ("AMW", "Suzuki", "Alto K10", "ICE", "Hatchback", 6.8),
        ("AMW", "Suzuki", "WagonR", "Hybrid", "Hatchback", 8.9),
        ("United Motors", "Perodua", "Axia", "ICE", "Hatchback", 8.2),
        ("United Motors", "Mitsubishi", "Xpander", "ICE", "SUV", 21.8),
        ("United Motors", "MG", "ZS EV", "EV", "SUV", 16.5),
        ("John Keells CG Auto", "BYD", "Dolphin", "EV", "Hatchback", 10.9),
        ("John Keells CG Auto", "BYD", "Atto 3", "EV", "SUV", 14.9),
        ("John Keells CG Auto", "BYD", "Seal", "EV", "Sedan", 26.5),
        ("Euro Motors", "Jetour", "Dashing", "ICE", "SUV", 17.5),
        ("Euro Motors", "Jetour", "T2", "ICE", "SUV", 23.5),
        ("Hayleys Mobility", "Jaecoo", "J7", "ICE", "SUV", 21.0),
        ("Toyota Lanka", "Toyota", "Raize", "ICE", "SUV", 13.8),
        ("Toyota Lanka", "Toyota", "Corolla Cross", "Hybrid", "SUV", 22.0),
        ("DIMO", "Mercedes-Benz", "C200", "Hybrid", "Sedan", 38.0),
        ("DIMO", "Mercedes-Benz", "EQE", "EV", "Sedan", 46.0),
        ("Prestige Automobile", "BMW", "X5", "ICE", "SUV", 52.0),
    ]
    return pd.DataFrame(
        sample,
        columns=["Distributor", "Brand", "Model", "Powertrain", "Body_Type", "Std_Price_Mn"],
    )


def plot_nine_box_positioning(df: pd.DataFrame):
    """Generate the 9-Box Scatter Plot (Y: ICE / Hybrid / EV, X: Price in LKR Mn)."""
    y_map = {"EV": 1.0, "Hybrid": 2.0, "ICE": 3.0}
    df = df.copy()
    df["Y_Base"] = df["Powertrain"].map(y_map)
    df = df.dropna(subset=["Y_Base", "Std_Price_Mn"])

    # Slight vertical jitter inside each band so overlapping dots stay readable
    rng = np.random.default_rng(42)
    df["Y_Plot"] = df["Y_Base"] + rng.uniform(-0.22, 0.22, size=len(df))

    max_x = max(df["Std_Price_Mn"].max() * 1.12, 35.0)

    fig, ax = plt.subplots(figsize=(14, 8.5), dpi=200)
    fig.patch.set_facecolor("#F8FAFC")
    ax.set_facecolor("#FFFFFF")

    # Shaded 9-box backgrounds
    tier_spans = [
        (0, BUDGET_MAX, "#F0FDFA", "BUDGET\n(< LKR 12M)"),
        (BUDGET_MAX, MIDRANGE_MAX, "#F8FAFC", "MID-RANGE\n(LKR 12M – 25M)"),
        (MIDRANGE_MAX, max_x, "#FEFCE8", "PREMIUM\n(> LKR 25M)"),
    ]
    for x0, x1, color, label in tier_spans:
        ax.axvspan(x0, x1, color=color, alpha=0.55, zorder=0)
        ax.text(
            (x0 + x1) / 2,
            3.56,
            label,
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color="#0F2041",
        )

    # Grid lines dividing the 9 boxes
    for xv in [BUDGET_MAX, MIDRANGE_MAX]:
        ax.axvline(xv, color="#94A3B8", linestyle="--", linewidth=1.3, zorder=1)
    for yv in [1.5, 2.5]:
        ax.axhline(yv, color="#94A3B8", linestyle="--", linewidth=1.3, zorder=1)

    # Plot each distributor in a distinct color
    distributors = sorted(df["Distributor"].unique())
    palette = plt.cm.tab10(np.linspace(0, 1, max(len(distributors), 10)))
    color_map = {d: palette[i % len(palette)] for i, d in enumerate(distributors)}

    for dist in distributors:
        sub = df[df["Distributor"] == dist]
        ax.scatter(
            sub["Std_Price_Mn"],
            sub["Y_Plot"],
            s=110,
            color=color_map[dist],
            edgecolors="#0F172A",
            linewidths=0.8,
            label=dist,
            zorder=4,
            alpha=0.92,
        )
        for _, row in sub.iterrows():
            ax.annotate(
                f"{row['Brand']} {row['Model']}",
                (row["Std_Price_Mn"], row["Y_Plot"]),
                xytext=(6, 4),
                textcoords="offset points",
                fontsize=7.8,
                color="#1E293B",
                zorder=5,
            )

    ax.set_xlim(0, max_x)
    ax.set_ylim(0.5, 3.72)
    ax.set_yticks([1.0, 2.0, 3.0])
    ax.set_yticklabels(["EV\n(100% Electric)", "HYBRID\n(Mild / Full / PHEV)", "ICE\n(Petrol / Diesel)"], fontsize=10.5, fontweight="bold", color="#0F2041")
    ax.set_xlabel("Standardized Brand-New Price (LKR Millions, VAT-Inclusive)", fontsize=11, fontweight="bold", color="#0F2041", labelpad=10)
    ax.set_title(
        "Sri Lanka Brand-New Automotive Market — 9-Box Product Positioning Map",
        fontsize=15,
        fontweight="bold",
        color="#0F2041",
        pad=32,
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(title="Distributor", bbox_to_anchor=(1.02, 1), loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="#CBD5E1")

    plt.tight_layout()
    out_file = OUTPUT_DIR / "nine_box_positioning_map.png"
    plt.savefig(out_file, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_file}")


def plot_portfolio_mix(df: pd.DataFrame):
    """Stacked horizontal bar chart of ICE / Hybrid / EV counts per Distributor."""
    counts = (
        df.groupby(["Distributor", "Powertrain"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["ICE", "Hybrid", "EV"], fill_value=0)
    )
    counts["Total"] = counts.sum(axis=1)
    counts = counts.sort_values("Total", ascending=True).drop(columns=["Total"])

    ax = counts.plot(
        kind="barh",
        stacked=True,
        figsize=(10, 6),
        color={"ICE": "#0F2041", "Hybrid": "#F59E0B", "EV": "#0D9488"},
        edgecolor="#FFFFFF",
    )
    ax.set_title("Brand-New Vehicle Portfolio Mix by Distributor (ICE vs. Hybrid vs. EV)", fontsize=13, fontweight="bold", color="#0F2041", pad=14)
    ax.set_xlabel("Number of Brand-New Models Offered", fontsize=10, fontweight="bold", color="#0F2041")
    ax.set_ylabel("")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()

    out_file = OUTPUT_DIR / "portfolio_mix_by_distributor.png"
    plt.savefig(out_file, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    data = load_data()
    plot_nine_box_positioning(data)
    plot_portfolio_mix(data)

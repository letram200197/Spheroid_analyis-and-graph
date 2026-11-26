import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ==========================================
# 0. Settings you may want to change
# ==========================================
CONDITION_LABEL = ""       # e.g. "APP695, 0.1 kPa, 0 hr fixed". Empty = use the cell file's folder name
Z_REF_MODE = "file"        # Reference plane for axial offset dZ: "file" (Z column of the boundary file), or "mean"/"median"/"midrange" of cell CZ
INNER_RING_FRAC = 0.6      # Faint dotted reference ring in panel A (fraction of R_eq)
RIM_FRAC = 0.8             # "Outer rim" threshold (fraction of R_eq)
N_LABEL_VOL = 3            # Number the N largest-volume cells ...
N_LABEL_INT = 2            # ... and the N brightest cells
SHOW_PLOTS = True          # False = only save files, don't open windows

# ==========================================
# 1. File Selection (pop-up dialogs, or pass paths as arguments)
# ==========================================
if len(sys.argv) >= 3:
    CELL_FILE, XY_FILE = sys.argv[1], sys.argv[2]
else:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    CELL_FILE = filedialog.askopenfilename(
        parent=root,
        title="Select the cell data file (e.g. Results_cells.xlsx)",
        filetypes=[("Cell data", ("*.xlsx", "*.xls", "*.csv")), ("All files", "*.*")],
    )
    if not CELL_FILE:
        root.destroy()
        sys.exit("No cell data file selected. Exiting.")

    XY_FILE = filedialog.askopenfilename(
        parent=root,
        title="Select the MIP boundary file (e.g. Results_xyz.csv)",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialdir=os.path.dirname(CELL_FILE),
    )
    root.destroy()
    if not XY_FILE:
        sys.exit("No boundary file selected. Exiting.")

out_dir = os.path.dirname(os.path.abspath(CELL_FILE))
stem = os.path.splitext(os.path.basename(CELL_FILE))[0]
OUTPUT_PREFIX = os.path.join(out_dir, f"{stem}_spheroid_analysis")
if not CONDITION_LABEL:
    CONDITION_LABEL = os.path.basename(out_dir)

print(f"Cell file: {CELL_FILE}")
print(f"XY file:   {XY_FILE}")

# ==========================================
# 2. Load & Clean Cell Data (.xlsx or .csv)
# ==========================================
if CELL_FILE.lower().endswith((".xlsx", ".xls")):
    df_cell = pd.read_excel(CELL_FILE)
else:
    df_cell = pd.read_csv(CELL_FILE)

# Handle both named headers ('CX', 'CY', 'CZ', 'Vol', 'intensity') and 'Unnamed' columns
if "CX" in df_cell.columns:
    df = df_cell[["CX", "CY", "CZ", "Vol", "intensity"]].copy()
else:
    df = df_cell.iloc[:, [4, 5, 6, 7, 12]].copy()
    df.columns = ["CX", "CY", "CZ", "Vol", "intensity"]

df.insert(0, "Cell_ID", df_cell.index.to_numpy() + 1)   # 1-based row number, used for the labels
for col in ["CX", "CY", "CZ", "Vol", "intensity"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
df = df.dropna(subset=["CX", "CY", "CZ"]).reset_index(drop=True)

# ==========================================
# 3. MIP Boundary -> Centroid, R_eq (2D); axial reference plane
# ==========================================
df_xy = pd.read_csv(XY_FILE)
df_xy.columns = [str(c).strip() for c in df_xy.columns]
lower = {c.lower(): c for c in df_xy.columns}
if "x" not in lower or "y" not in lower:
    raise ValueError(f"Could not find X and Y columns in {XY_FILE}. Found: {df_xy.columns.tolist()}")
xs = pd.to_numeric(df_xy[lower["x"]], errors="coerce")
ys = pd.to_numeric(df_xy[lower["y"]], errors="coerce")
ok = xs.notna() & ys.notna()
xs, ys = xs[ok], ys[ok]
if xs.empty:
    raise ValueError(f"No numeric X/Y values found in {XY_FILE}.")

# Case 1: file is a Fiji measurement of the MIP outline (columns Area, X, Y = area + centroid)
area_val = np.nan
if "area" in lower:
    area_ok = pd.to_numeric(df_xy[lower["area"]], errors="coerce")[ok].dropna()
    if not area_ok.empty:
        area_val = float(area_ok.iloc[0])

if area_val > 0:
    first = area_ok.index[0]
    cx0, cy0 = float(xs.loc[first]), float(ys.loc[first])
    R_eq = float(np.sqrt(area_val / np.pi))          # radius of the circle with the same area as the MIP outline
    geometry_source = f"MIP area {area_val:.0f} px^2 + centroid from boundary file"
else:
    # Case 2: file lists outline coordinates -> use their bounding box (fallback: cell cloud extent)
    x_min_c, x_max_c = df["CX"].min(), df["CX"].max()
    y_min_c, y_max_c = df["CY"].min(), df["CY"].max()
    x_min_b, x_max_b = xs.min(), xs.max()
    y_min_b, y_max_b = ys.min(), ys.max()

    span_ratio_x = (x_max_b - x_min_b) / max(x_max_c - x_min_c, 1e-6)
    span_ratio_y = (y_max_b - y_min_b) / max(y_max_c - y_min_c, 1e-6)
    overlap_x = (x_max_b >= x_min_c) and (x_min_b <= x_max_c)
    overlap_y = (y_max_b >= y_min_c) and (y_min_b <= y_max_c)

    if overlap_x and overlap_y and span_ratio_x >= 0.5 and span_ratio_y >= 0.5:
        x_min, x_max, y_min, y_max = x_min_b, x_max_b, y_min_b, y_max_b
        geometry_source = "bounding box of boundary file"
    else:
        x_min, x_max, y_min, y_max = x_min_c, x_max_c, y_min_c, y_max_c
        geometry_source = "WARNING: cell cloud extent (boundary file unusable)"

    cx0 = 0.5 * (x_min + x_max)
    cy0 = 0.5 * (y_min + y_max)
    R_eq = float(np.sqrt(0.5 * (x_max - x_min) * 0.5 * (y_max - y_min)))

if R_eq <= 0:
    raise ValueError("R_eq is zero - check the boundary file.")

# Axial reference plane
z_source = Z_REF_MODE
z0 = np.nan
if Z_REF_MODE == "file":
    z_cols = [c for c in df_xy.columns if c.lower().startswith("z")]
    if z_cols:
        z_vals = pd.to_numeric(df_xy[z_cols[0]], errors="coerce").dropna()
        if not z_vals.empty:
            z0 = float(z_vals.mean())          # single-row file -> that Z value
    if np.isnan(z0):
        print("NOTE: no usable Z column in the boundary file - using the mean cell CZ instead.")
        z_source = "mean (no Z in file)"
        z0 = df["CZ"].mean()
elif Z_REF_MODE == "median":
    z0 = df["CZ"].median()
elif Z_REF_MODE == "midrange":
    z0 = 0.5 * (df["CZ"].min() + df["CZ"].max())
else:
    z0 = df["CZ"].mean()

df["dZ"] = df["CZ"] - z0                                         # axial offset (slices)
df["r_xy"] = np.hypot(df["CX"] - cx0, df["CY"] - cy0)            # 2D lateral radial distance (px)
df["r_norm"] = df["r_xy"] / R_eq

# ==========================================
# 4. Radial Shells & Export Tables
# ==========================================
bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, np.inf]
labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0", ">1.0"]
df["Shell"] = pd.cut(df["r_norm"], bins=bins, labels=labels, include_lowest=True)

summary = (
    df.groupby("Shell", observed=False)
    .agg(
        Cell_Count=("r_norm", "count"),
        Mean_Vol=("Vol", "mean"),
        Mean_Intensity=("intensity", "mean"),
    )
    .reindex(labels)
    .reset_index()
)
summary["Cell_Count"] = summary["Cell_Count"].fillna(0).astype(int)
summary["Percentage"] = (summary["Cell_Count"] / len(df) * 100) if len(df) > 0 else 0.0

print(f"Total Cells: {len(df)} | Centroid: ({cx0:.1f}, {cy0:.1f}) | R_eq: {R_eq:.1f} px ({geometry_source}) | Z ref ({z_source}): {z0:.2f}")
print(summary.to_string(index=False))

summary.to_csv(f"{OUTPUT_PREFIX}_shell_summary.csv", index=False)
df.to_csv(f"{OUTPUT_PREFIX}_per_cell_metrics.csv", index=False)

# ==========================================
# 5. Figure 1: 2-Panel Lateral Map + Radial/Axial Distribution
# ==========================================
# Marker size scales with cell volume (5th-95th percentile range)
vol = df["Vol"].fillna(df["Vol"].median()).fillna(1.0).to_numpy()
lo, hi = np.percentile(vol, [5, 95])
if hi > lo:
    sizes = 20 + 160 * np.clip((vol - lo) / (hi - lo), 0, 1)
else:
    sizes = np.full(len(df), 70.0)

# Cells to number: largest volume + brightest
label_idx = set(df["Vol"].nlargest(N_LABEL_VOL).index) | set(df["intensity"].nlargest(N_LABEL_INT).index)

def add_labels(ax, xcol, ycol):
    for i in label_idx:
        ax.annotate(str(int(df.at[i, "Cell_ID"])), (df.at[i, xcol], df.at[i, ycol]),
                    xytext=(4, -8), textcoords="offset points", fontsize=7, color="#222222")

SLATE, GREYC = "#5B6B7F", "#9AA0A6"
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6.8), layout="constrained")

# ---- Panel A: XY positions coloured by axial offset ----
dz_lim = max(float(df["dZ"].abs().max()), 1e-6)
sc1 = ax1.scatter(df["CX"], df["CY"], c=df["dZ"], cmap="coolwarm", vmin=-dz_lim, vmax=dz_lim,
                  s=sizes, alpha=0.9, edgecolors="#333333", linewidth=0.5, zorder=3)
ax1.add_patch(patches.Circle((cx0, cy0), R_eq, fill=False, edgecolor=SLATE, linewidth=1.8,
                             label=f"100% R_eq ({R_eq:.0f} px)", zorder=2))
ax1.add_patch(patches.Circle((cx0, cy0), RIM_FRAC * R_eq, fill=False, edgecolor=GREYC, linestyle="--",
                             linewidth=1.2, label=f"{RIM_FRAC * 100:.0f}% R_eq ({RIM_FRAC * R_eq:.0f} px)", zorder=2))
ax1.add_patch(patches.Circle((cx0, cy0), INNER_RING_FRAC * R_eq, fill=False, edgecolor="#B8BDC2",
                             linestyle=":", linewidth=1.0, zorder=2))
ax1.scatter([cx0], [cy0], marker="*", s=260, color="#F5A623", edgecolors="black", linewidth=1.0,
            label="Spheroid Centroid", zorder=5)
add_labels(ax1, "CX", "CY")

half = max(1.27 * R_eq, 1.1 * df["r_xy"].max())
ax1.set_xlim(cx0 - half, cx0 + half)
ax1.set_ylim(cy0 + half, cy0 - half)              # inverted Y = image (Fiji) orientation
ax1.set_aspect("equal", adjustable="box")
ax1.set_title(f"A. Lateral (XY) Cell Positions ({CONDITION_LABEL}; n = {len(df)})", fontsize=11)
ax1.set_xlabel("X Coordinate (px)", fontsize=10)
ax1.set_ylabel("Y Coordinate (px)", fontsize=10)
ax1.grid(True, linestyle=":", alpha=0.4)
ax1.legend(loc="upper left", fontsize=8, framealpha=0.9)
cb1 = fig.colorbar(sc1, ax=ax1, fraction=0.046, pad=0.03)
cb1.set_label(f"Axial Offset \u0394Z (slices from Z={z0:.2f})", fontsize=9)

# ---- Panel B: radial distance vs axial offset, coloured by intensity ----
sc2 = ax2.scatter(df["r_xy"], df["dZ"], c=df["intensity"], cmap="viridis",
                  s=sizes, alpha=0.85, edgecolors="#333333", linewidth=0.4, zorder=3)
ax2.axhline(0, color="#8FA8BF", linewidth=1.0, zorder=1)
ax2.axvline(R_eq, color="red", linestyle="--", linewidth=1.5, zorder=2,
            label=f"MIP Boundary R_eq = {R_eq:.1f} px")
ax2.axvline(RIM_FRAC * R_eq, color="#5B7083", linestyle=":", linewidth=1.3, zorder=2,
            label=f"Outer Rim Threshold ({RIM_FRAC} R_eq = {RIM_FRAC * R_eq:.1f} px)")
add_labels(ax2, "r_xy", "dZ")

ax2.set_xlim(0, max(1.22 * R_eq, 1.05 * df["r_xy"].max()))
ax2.set_title("B. Radial vs. Axial (Z) Distribution & Intensity", fontsize=11)
ax2.set_xlabel("2D Lateral Radial Distance r_XY (px)", fontsize=10)
ax2.set_ylabel(f"Axial Offset \u0394Z = CZ \u2212 {z0:.2f} (slices)", fontsize=10)
ax2.grid(True, linestyle=":", alpha=0.4)
ax2.legend(loc="upper left", fontsize=8, framealpha=0.9)
cb2 = fig.colorbar(sc2, ax=ax2, fraction=0.046, pad=0.03)
cb2.set_label("Mean Fluorescence Intensity (a.u.)", fontsize=9)

fig.savefig(f"{OUTPUT_PREFIX}_spatial_panels.png", dpi=300)

# ==========================================
# 6. Figure 2: Radial Shell Bar Chart
# ==========================================
fig2, ax = plt.subplots(figsize=(7.5, 4.5))
bars = ax.bar(summary["Shell"], summary["Cell_Count"], color="#3B7EA1",
              edgecolor="#1F4E68", linewidth=1.0, width=0.62)

ymax_bar = summary["Cell_Count"].max()
ax.set_ylim(0, ymax_bar * 1.18 if ymax_bar > 0 else 10)
for bar, (_, row) in zip(bars, summary.iterrows()):
    ax.text(bar.get_x() + bar.get_width() / 2.0, bar.get_height() + ymax_bar * 0.025,
            f"{int(row['Cell_Count'])}\n({row['Percentage']:.1f}%)",
            ha="center", va="bottom", fontsize=8.5, color="#222222")

ax.set_title("Cell Distribution by Normalized Radial Shell (r_XY / R_eq)", fontsize=12, fontweight="bold", pad=12)
ax.set_xlabel("Normalized Radial Shell (r_XY / R_eq)", fontsize=10, fontweight="bold", labelpad=8)
ax.set_ylabel("Cell Count", fontsize=10, fontweight="bold", labelpad=8)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.yaxis.grid(True, linestyle="--", alpha=0.4)
ax.set_axisbelow(True)
fig2.tight_layout()
fig2.savefig(f"{OUTPUT_PREFIX}_bar_chart.png", dpi=300)

print(f"\nSaved results to: {out_dir}")
if SHOW_PLOTS:
    plt.show()
else:
    plt.close("all")

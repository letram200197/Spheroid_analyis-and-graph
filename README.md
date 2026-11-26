# Spheroid Analysis

Radial and axial distribution of cells in a 3D spheroid, from cell-centroid measurements and the
spheroid's 2D MIP (maximum-intensity-projection) outline. The script produces a two-panel figure,
a radial-shell bar chart, and two summary tables.

![Example output](examples/output/Results_cells_spheroid_analysis_spatial_panels.png)

*Example output from the synthetic data in `examples/` (not real measurements).*

## What it computes

| Quantity | Definition |
|---|---|
| Centroid (`cx0`, `cy0`) | X, Y from the boundary file |
| `R_eq` | Radius of the circle with the same area as the MIP outline: `sqrt(Area / pi)` |
| `r_xy` | 2D lateral distance of each cell from the centroid: `hypot(CX - cx0, CY - cy0)` (px) |
| `r_norm` | `r_xy / R_eq` |
| `dZ` | Axial offset: `CZ - Z_ref` (slices) |
| Shell | `r_norm` binned into 0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0, >1.0 |

**Panel A:** XY positions, coloured by `dZ`, with the 100 % and 80 % `R_eq` circles and the centroid.
**Panel B:** `r_xy` against `dZ`, coloured by mean fluorescence intensity. Marker size follows cell volume in both panels.

## Installation

Python 3.9 or newer.

```bash
git clone https://github.com/<your-username>/spheroid-analysis.git
cd spheroid-analysis

# pip
python -m pip install -r requirements.txt

# or conda
conda env create -f environment.yml
conda activate spheroid-analysis
```

`tkinter` (used for the file pickers) ships with Python on Windows and macOS. On Linux: `sudo apt install python3-tk`.

## Usage

**With file pickers** (first the cell file, then the boundary file):

```bash
python spheroid_analysis.py
```

**With paths** (no pop-ups, good for scripts and remote machines):

```bash
python spheroid_analysis.py path/to/Results_cells.xlsx path/to/Results_xy.csv
```

**Try it on the bundled synthetic example:**

```bash
python spheroid_analysis.py examples/Results_cells.csv examples/Results_xy.csv
```

Outputs are written next to the cell file. On a machine without a display, run with `MPLBACKEND=Agg`
(and `SHOW_PLOTS = False` in the script) so no plot windows are opened.

## Input files

### 1. Cell file (`.xlsx`, `.xls` or `.csv`), one row per cell

Needs the columns `CX`, `CY`, `CZ` (centroid, px / slices), `Vol` and `intensity`.
If the headers are blank (the table has "Unnamed" columns), the script reads them by position:
columns 5, 6, 7, 8 and 13 (zero-based 4, 5, 6, 7, 12). Rows with a missing `CX`, `CY` or `CZ` are dropped.
Cells are numbered by their row position (1, 2, 3, ...), and those numbers are the labels in the figure.

### 2. Boundary file (`.csv`), MIP outline of the spheroid

Either of these layouts works:

| Layout | Columns | How it is used |
|---|---|---|
| Measurement summary (one row) | `Area`, `X`, `Y`, optional `Z` | `R_eq = sqrt(Area / pi)`, centroid = (`X`, `Y`) |
| Outline coordinates (many rows) | `X`, `Y` | Bounding box: centre = box centre, `R_eq = sqrt(rx * ry)` |

If the boundary file does not cover the cells (too small or offset), the script falls back to the cell-cloud
extent and prints a `WARNING` in the summary line.

## Outputs

For a cell file called `Results_cells.xlsx`:

| File | Content |
|---|---|
| `Results_cells_spheroid_analysis_spatial_panels.png` | Two-panel figure (300 dpi) |
| `Results_cells_spheroid_analysis_bar_chart.png` | Cell count per radial shell |
| `Results_cells_spheroid_analysis_per_cell_metrics.csv` | `Cell_ID, CX, CY, CZ, Vol, intensity, dZ, r_xy, r_norm, Shell` |
| `Results_cells_spheroid_analysis_shell_summary.csv` | Count, mean volume, mean intensity and percentage per shell |

## Settings

Edit the constants at the top of `spheroid_analysis.py`:

| Setting | Default | Meaning |
|---|---|---|
| `CONDITION_LABEL` | `""` | Text in the panel A title. Empty = name of the cell file's folder |
| `Z_REF_MODE` | `"file"` | Reference plane for `dZ`: `"file"` (Z column of the boundary file), or `"mean"`, `"median"`, `"midrange"` of the cell `CZ` values. If the file has no Z, the mean is used |
| `INNER_RING_FRAC` | `0.6` | Radius of the faint dotted ring in panel A (fraction of `R_eq`) |
| `RIM_FRAC` | `0.8` | Outer-rim threshold (fraction of `R_eq`) |
| `N_LABEL_VOL` / `N_LABEL_INT` | `3` / `2` | Number of largest-volume and brightest cells to label |
| `SHOW_PLOTS` | `True` | `False` = save files only |

## Notes and limitations

- Distances are in pixels and Z in slices, as exported. Nothing is converted to micrometres, so scale
  the values yourself if you need physical units.
- `R_eq` is a 2D radius from the MIP, while cell positions are 3D centroids, so a few cells can have
  `r_norm` slightly above 1.
- Choose `Z_REF_MODE` with care. A Z value that sits far from the cells' Z range (for example a fixed slice
  number) makes almost every `dZ` the same sign and washes out the colour scale in panel A.
- Shell counts are raw counts, not densities. Outer shells cover a larger area, so more cells there does not
  by itself mean enrichment.

## Troubleshooting

- **`ImportError: ... openpyxl`:** `python -m pip install openpyxl` (needed to read `.xlsx`).
- **`ModuleNotFoundError`:** install into the same Python that runs the script, with `python -m pip install -r requirements.txt`.
- **Windows, `Errno 22 Invalid argument` when pressing the VS Code run button:** the path has spaces and VS Code adds extra quotes.
  Run from a terminal instead: `python spheroid_analysis.py`, or move the project to a path without spaces.
- **A file picker does not appear:** check the taskbar, it can open behind another window.

## License

MIT, see [LICENSE](LICENSE).

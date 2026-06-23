"""
SERS Baseline Correction (PyQt6 + pybaselines).

Input  :
  - .txt : col 0 = (index or) wavenumber, cols 1..N = spectra (whitespace separated).
           If the first column is monotonically increasing 1,2,3... it is treated
           as a row index and the second column becomes the wavenumber.
  - .csv : Raman mapping file with two metadata lines ("X num,<nx>" / "Y num,<ny>"),
           a header row "X,Y,<wn1>,<wn2>,...", and one data row per pixel
           "<x>,<y>,<intensity1>,<intensity2>,...".

Output : <name>_corrected.csv
  - TXT input  → wavenumber, spec_..., mean, sd.
  - CSV mapping input → preserves the source X num / Y num / X,Y,wn layout
    with one corrected spectrum per pixel row.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QSpinBox, QVBoxLayout, QFormLayout,
    QSplitter, QMessageBox, QGroupBox, QCheckBox, QStatusBar,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
from matplotlib.figure import Figure
from pybaselines import Baseline


@dataclass
class MappingMeta:
    """Spatial layout of a Raman 2-D mapping CSV — needed to save corrected
    output back in the same X num/Y num/X,Y,wn pixel-row format the instrument
    produced."""
    nx: int                 # value of the "X num,<n>" header
    ny: int                 # value of the "Y num,<n>" header
    xy: np.ndarray          # (n_pixels, 2) X, Y coordinates per pixel, in load order
    trailing_comma: bool    # whether the source file appended an empty trailing column


def load_sers_txt(path: Path) -> tuple[pd.DataFrame, MappingMeta | None]:
    df = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    if df.shape[1] < 2:
        raise ValueError(f"expected >=2 columns, found {df.shape[1]}")

    first = df.iloc[:, 0].to_numpy()
    if (
        df.shape[1] >= 3
        and np.allclose(first, np.arange(1, len(first) + 1))
    ):
        df = df.iloc[:, 1:].reset_index(drop=True)

    n = df.shape[1] - 1
    df.columns = ["wavenumber"] + [f"spec_{i:02d}" for i in range(1, n + 1)]
    return df, None


def load_sers_csv_mapping(path: Path) -> tuple[pd.DataFrame, MappingMeta | None]:
    """Load Raman mapping CSV: 2 metadata lines + 'X,Y,wn...' header + pixel rows.

    Falls back to the plain whitespace/csv layout used by load_sers_txt when the
    file does not start with the 'X num' / 'Y num' header (so a CSV that simply
    mirrors the TXT layout still works).
    """
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        first = fh.readline()
        second = fh.readline()
        header_line = fh.readline()

    if not first.lower().lstrip().startswith("x num"):
        try:
            df = pd.read_csv(path, header=None)
        except Exception:
            df = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
        if df.shape[1] < 2:
            raise ValueError(f"expected >=2 columns, found {df.shape[1]}")
        n = df.shape[1] - 1
        df.columns = ["wavenumber"] + [f"spec_{i:02d}" for i in range(1, n + 1)]
        return df, None

    def _meta_int(line: str, key: str) -> int:
        toks = [t.strip() for t in line.split(",")]
        if len(toks) < 2:
            raise ValueError(f"could not parse '{key}' metadata from line: {line!r}")
        try:
            return int(float(toks[1]))
        except ValueError as e:
            raise ValueError(f"could not parse '{key}' value: {e}") from e
    nx = _meta_int(first, "X num")
    ny = _meta_int(second, "Y num")

    raw_tokens = header_line.rstrip("\r\n").split(",")
    trailing_comma = len(raw_tokens) > 0 and raw_tokens[-1].strip() == ""
    header_tokens = [t.strip() for t in raw_tokens]
    while header_tokens and header_tokens[-1] == "":
        header_tokens.pop()
    if (
        len(header_tokens) < 3
        or header_tokens[0].upper() != "X"
        or header_tokens[1].upper() != "Y"
    ):
        raise ValueError("mapping CSV header must start with 'X,Y,<wavenumbers...>'")
    try:
        wn = np.asarray(header_tokens[2:], dtype=float)
    except ValueError as e:
        raise ValueError(f"could not parse wavenumbers from header: {e}") from e

    data = pd.read_csv(path, skiprows=3, header=None).dropna(axis=1, how="all").to_numpy()
    expected_cols = len(header_tokens)
    if data.shape[1] != expected_cols:
        raise ValueError(
            f"data row width {data.shape[1]} does not match header width {expected_cols}"
        )

    xy = data[:, :2]
    spectra = data[:, 2:].T

    col_names = ["wavenumber"] + [
        f"spec_x{xy[i, 0]:g}_y{xy[i, 1]:g}" for i in range(spectra.shape[1])
    ]
    block = np.column_stack([wn, spectra])
    df = pd.DataFrame(block, columns=col_names)

    meta = MappingMeta(nx=nx, ny=ny, xy=xy.astype(float), trailing_comma=trailing_comma)
    return df, meta


def load_sers_file(path: Path) -> tuple[pd.DataFrame, MappingMeta | None]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_sers_csv_mapping(path)
    return load_sers_txt(path)


def save_corrected_mapping(
    path: str | Path,
    wavenumber: np.ndarray,
    corrected: np.ndarray,
    meta: MappingMeta,
) -> None:
    """Write the baseline-corrected mapping back in the source X num / Y num /
    X,Y,wn... layout. corrected is shape (n_wavenumbers, n_pixels), same order
    as meta.xy."""
    n_pix = meta.xy.shape[0]
    if corrected.shape[1] != n_pix:
        raise ValueError(
            f"corrected has {corrected.shape[1]} spectra but meta has {n_pix} pixels"
        )
    if corrected.shape[0] != wavenumber.shape[0]:
        raise ValueError("wavenumber length does not match corrected row count")

    def _fmt(v: float) -> str:
        # match the source CSV: integer-valued coords print without a decimal
        if float(v).is_integer():
            return str(int(v))
        return f"{v:g}"

    tail = "," if meta.trailing_comma else ""
    wn_str = ",".join(f"{w:g}" for w in wavenumber)

    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(f"X num,{meta.nx}\n")
        fh.write(f"Y num,{meta.ny}\n")
        fh.write(f"X,Y,{wn_str}{tail}\n")
        for i in range(n_pix):
            x_s = _fmt(meta.xy[i, 0])
            y_s = _fmt(meta.xy[i, 1])
            vals = ",".join(f"{v:.6f}" for v in corrected[:, i])
            fh.write(f"{x_s},{y_s},{vals}{tail}\n")


def despike_spectra(
    spectra: np.ndarray, threshold: float = 7.0, window: int = 5
) -> np.ndarray:
    """Remove narrow spikes (cosmic rays / detector glitches) from each spectrum.

    Uses a Hampel filter: compare every point to a rolling median; a point that
    deviates by more than `threshold` robust standard deviations (scaled MAD) is
    treated as a spike and replaced by the local median. Real Raman bands span
    several points and stay close to their neighbourhood median, so they survive;
    1-2 point spikes do not. `window` is the rolling-median width in points
    (forced odd). Operates column-by-column; returns a new array.
    """
    spectra = np.asarray(spectra, dtype=float)
    n = spectra.shape[0]
    if n < 3:
        return spectra.copy()
    k = max(3, int(window))
    if k % 2 == 0:
        k += 1
    if k > n:
        k = n if n % 2 == 1 else n - 1

    from scipy.signal import medfilt

    out = spectra.copy()
    for j in range(out.shape[1]):
        y = out[:, j]
        med = medfilt(y, kernel_size=k)
        dev = np.abs(y - med)
        # robust sigma estimate; 1.4826 makes MAD a consistent std estimator
        sigma = 1.4826 * np.median(dev)
        if sigma <= 0:
            # Very clean data: most residuals are exactly 0, so the MAD collapses.
            # Fall back to a scale from the non-zero residuals so only gross
            # spikes (≫ local curvature) are caught, not smooth peak tips.
            nz = dev[dev > 0]
            if nz.size == 0:
                continue
            sigma = 1.4826 * np.median(nz)
            if sigma <= 0:
                continue
        spikes = dev > threshold * sigma
        y[spikes] = med[spikes]
    return out


def compute_baselines(
    wn: np.ndarray, spectra: np.ndarray, algo: str, lam: float, p: float, max_iter: int
) -> np.ndarray:
    fitter = Baseline(x_data=wn)
    out = np.empty_like(spectra, dtype=float)
    for i in range(spectra.shape[1]):
        y = spectra[:, i].astype(float)
        if algo == "ALS":
            bkg, _ = fitter.asls(y, lam=lam, p=p, max_iter=max_iter)
        elif algo == "airPLS":
            bkg, _ = fitter.airpls(y, lam=lam, max_iter=max_iter)
        else:
            raise ValueError(f"unknown algorithm: {algo}")
        out[:, i] = bkg
    return out


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SERS Baseline Correction")
        self.resize(1280, 780)

        self.df: pd.DataFrame | None = None
        self.spec_cols: list[str] = []
        self.baselines: np.ndarray | None = None
        self.corrected: np.ndarray | None = None
        self.processed: np.ndarray | None = None   # spectra after despiking (raw if off)
        self._preview: np.ndarray | None = None     # cached despiked array for live raw plot
        self._preview_key: tuple | None = None      # (threshold, window) the cache was built with
        self.current_path: Path | None = None
        self.map_meta: MappingMeta | None = None

        self.btn_open = QPushButton("Open TXT / CSV…")
        self.btn_open.clicked.connect(self.open_file)
        self.lbl_file = QLabel("(no file loaded)")
        self.lbl_file.setWordWrap(True)

        self.chk_despike = QCheckBox("Remove spikes (despike)")
        self.chk_despike.setChecked(True)
        self.chk_despike.setToolTip(
            "Remove narrow cosmic-ray / detector spikes before baseline fitting."
        )
        self.chk_despike.toggled.connect(self._despike_toggled)

        self.spn_spike = QDoubleSpinBox()
        self.spn_spike.setRange(2.0, 30.0)
        self.spn_spike.setDecimals(1)
        self.spn_spike.setValue(7.0)
        self.spn_spike.setSingleStep(0.5)
        self.spn_spike.setToolTip(
            "Sensitivity: lower removes more (also riskier for sharp real peaks)."
        )
        self.spn_spike.valueChanged.connect(self._schedule_preview)

        self.spn_spwin = QSpinBox()
        self.spn_spwin.setRange(3, 21)
        self.spn_spwin.setSingleStep(2)
        self.spn_spwin.setValue(5)
        self.spn_spwin.setToolTip("Rolling-median width in points (odd).")
        self.spn_spwin.valueChanged.connect(self._schedule_preview)

        # debounce live despike preview so dragging a spinbox doesn't recompute
        # on every intermediate value
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(180)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self.cmb_algo = QComboBox()
        self.cmb_algo.addItems(["ALS", "airPLS"])
        self.cmb_algo.currentTextChanged.connect(self._algo_changed)

        self.spn_lam = QDoubleSpinBox()
        self.spn_lam.setRange(1e2, 1e10)
        self.spn_lam.setDecimals(0)
        self.spn_lam.setValue(1e5)
        self.spn_lam.setSingleStep(1e4)

        self.spn_p = QDoubleSpinBox()
        self.spn_p.setRange(1e-4, 0.5)
        self.spn_p.setDecimals(4)
        self.spn_p.setValue(0.01)
        self.spn_p.setSingleStep(0.005)

        self.spn_iter = QSpinBox()
        self.spn_iter.setRange(5, 500)
        self.spn_iter.setValue(50)

        self.btn_apply = QPushButton("Apply baseline")
        self.btn_apply.clicked.connect(self.apply_baseline)
        self.btn_apply.setEnabled(False)

        self.cmb_spec = QComboBox()
        self.cmb_spec.addItem("All overlay")
        self.cmb_spec.currentIndexChanged.connect(self._update_plot)

        self.chk_show_baseline = QCheckBox("Show baseline overlay")
        self.chk_show_baseline.setChecked(True)
        self.chk_show_baseline.toggled.connect(self._update_plot)

        self.chk_show_mean = QCheckBox("Show mean ± sd on corrected")
        self.chk_show_mean.setChecked(False)
        self.chk_show_mean.toggled.connect(self._update_plot)

        self.btn_save = QPushButton("Save corrected CSV…")
        self.btn_save.clicked.connect(self.save_corrected)
        self.btn_save.setEnabled(False)

        params = QFormLayout()
        params.addRow(self.chk_despike)
        params.addRow("spike thr", self.spn_spike)
        params.addRow("spike win", self.spn_spwin)
        params.addRow("Algorithm", self.cmb_algo)
        params.addRow("λ (smoothness)", self.spn_lam)
        params.addRow("p (asymmetry)", self.spn_p)
        params.addRow("max iter", self.spn_iter)
        params_group = QGroupBox("Baseline parameters")
        params_group.setLayout(params)

        view = QFormLayout()
        view.addRow("Spectrum", self.cmb_spec)
        view.addRow(self.chk_show_baseline)
        view.addRow(self.chk_show_mean)
        view_group = QGroupBox("View")
        view_group.setLayout(view)

        left = QVBoxLayout()
        left.addWidget(self.btn_open)
        left.addWidget(self.lbl_file)
        left.addSpacing(6)
        left.addWidget(params_group)
        left.addWidget(self.btn_apply)
        left.addSpacing(6)
        left.addWidget(view_group)
        left.addStretch(1)
        left.addWidget(self.btn_save)

        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(290)

        self.fig = Figure(figsize=(8, 6), constrained_layout=True)
        self.ax_raw = self.fig.add_subplot(2, 1, 1)
        self.ax_cor = self.fig.add_subplot(2, 1, 2, sharex=self.ax_raw)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavToolbar(self.canvas, self)

        plot_widget = QWidget()
        pv = QVBoxLayout(plot_widget)
        pv.addWidget(self.toolbar)
        pv.addWidget(self.canvas)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(plot_widget)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())

        self._algo_changed(self.cmb_algo.currentText())
        self._despike_toggled(self.chk_despike.isChecked())
        self._update_plot()

    def _algo_changed(self, name: str) -> None:
        self.spn_p.setEnabled(name == "ALS")

    def _despike_toggled(self, on: bool) -> None:
        self.spn_spike.setEnabled(on)
        self.spn_spwin.setEnabled(on)
        self._schedule_preview()

    def _schedule_preview(self) -> None:
        """Queue a debounced refresh of the live despike preview."""
        if self.df is None:
            return
        self._preview_timer.start()

    def _refresh_preview(self) -> None:
        self._update_plot()
        if self.corrected is not None:
            self.statusBar().showMessage(
                "Despike preview updated — press Apply to refit the corrected plot", 4000
            )

    def _displayed_raw(self) -> tuple[np.ndarray, bool]:
        """Spectra for the top (Raw) plot, honouring the current despike settings.
        Result is cached by (threshold, window) so plain redraws stay cheap."""
        raw = self.df[self.spec_cols].to_numpy(dtype=float)
        if not self.chk_despike.isChecked():
            return raw, False
        key = (round(float(self.spn_spike.value()), 4), int(self.spn_spwin.value()))
        if self._preview is None or self._preview_key != key:
            try:
                self._preview = despike_spectra(raw, threshold=key[0], window=key[1])
                self._preview_key = key
            except Exception:
                return raw, False
        return self._preview, True

    def open_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open SERS data",
            str(Path.cwd()),
            "Raman data (*.txt *.csv);;Text files (*.txt);;CSV files (*.csv);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            df, meta = load_sers_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Load error", f"{path.name}\n{e}")
            return
        self.df = df
        self.current_path = path
        self.map_meta = meta
        self.spec_cols = [c for c in df.columns if c != "wavenumber"]
        self.baselines = None
        self.corrected = None
        self.processed = None
        self._preview = None
        self._preview_key = None

        self.cmb_spec.blockSignals(True)
        self.cmb_spec.clear()
        self.cmb_spec.addItem("All overlay")
        # Avoid populating one entry per pixel for large mappings — the combo
        # becomes useless and slow. Cap individual entries; "All overlay" still
        # works, and the user can plot the mean.
        if len(self.spec_cols) <= 200:
            for c in self.spec_cols:
                self.cmb_spec.addItem(c)
        self.cmb_spec.blockSignals(False)

        kind = "mapping" if meta is not None else "stack"
        self.lbl_file.setText(
            f"{path.name}\n({len(df)} pts × {len(self.spec_cols)} {kind})"
        )
        self.btn_apply.setEnabled(True)
        self.btn_save.setEnabled(False)
        self._update_plot()
        self.statusBar().showMessage(f"Loaded {path.name}", 5000)

    def apply_baseline(self) -> None:
        if self.df is None:
            return
        wn = self.df["wavenumber"].to_numpy(dtype=float)
        Y = self.df[self.spec_cols].to_numpy(dtype=float)
        algo = self.cmb_algo.currentText()
        lam = float(self.spn_lam.value())
        p = float(self.spn_p.value())
        it = int(self.spn_iter.value())

        despike = self.chk_despike.isChecked()
        if despike:
            self.statusBar().showMessage("Removing spikes…")
            QApplication.processEvents()
            try:
                Y = despike_spectra(
                    Y,
                    threshold=float(self.spn_spike.value()),
                    window=int(self.spn_spwin.value()),
                )
            except Exception as e:
                QMessageBox.critical(self, "Despike error", str(e))
                self.statusBar().showMessage("Despike failed", 5000)
                return
        self.processed = Y

        self.statusBar().showMessage(f"Fitting {algo} baseline…")
        QApplication.processEvents()
        try:
            B = compute_baselines(wn, Y, algo, lam, p, it)
        except Exception as e:
            QMessageBox.critical(self, "Baseline error", str(e))
            self.statusBar().showMessage("Baseline fit failed", 5000)
            return
        self.baselines = B
        self.corrected = Y - B
        self.btn_save.setEnabled(True)
        self._update_plot()
        spike_msg = "despike on, " if despike else ""
        self.statusBar().showMessage(
            f"{algo} applied  ({spike_msg}λ={lam:g}, p={p:g}, iter≤{it})", 6000
        )

    def _update_plot(self) -> None:
        self.ax_raw.clear()
        self.ax_cor.clear()

        if self.df is None:
            self.ax_raw.set_title("Raw — load a TXT or CSV to begin")
            self.ax_cor.set_title("Corrected")
            self._format_axes()
            self.canvas.draw_idle()
            return

        wn = self.df["wavenumber"].to_numpy()
        Y, despiked = self._displayed_raw()
        idx = self.cmb_spec.currentIndex()
        show_b = self.chk_show_baseline.isChecked()
        show_m = self.chk_show_mean.isChecked()

        if idx <= 0:
            for i, c in enumerate(self.spec_cols):
                self.ax_raw.plot(wn, Y[:, i], lw=0.7, alpha=0.7)
            if self.baselines is not None and show_b:
                for i in range(self.baselines.shape[1]):
                    self.ax_raw.plot(wn, self.baselines[:, i], lw=0.6, ls="--", alpha=0.5, color="k")
            if self.corrected is not None:
                if show_m:
                    mean = self.corrected.mean(axis=1)
                    sd = self.corrected.std(axis=1, ddof=1)
                    self.ax_cor.fill_between(wn, mean - sd, mean + sd, alpha=0.25, color="C0", label="±1 sd")
                    self.ax_cor.plot(wn, mean, lw=1.2, color="C0", label="mean")
                    self.ax_cor.legend(loc="best", fontsize=8)
                else:
                    for i in range(self.corrected.shape[1]):
                        self.ax_cor.plot(wn, self.corrected[:, i], lw=0.7, alpha=0.7)
        else:
            i = idx - 1
            c = self.spec_cols[i]
            self.ax_raw.plot(wn, Y[:, i], lw=1.0, label=f"raw {c}", color="C0")
            if self.baselines is not None and show_b:
                self.ax_raw.plot(wn, self.baselines[:, i], lw=1.0, ls="--", color="C3", label="baseline")
            self.ax_raw.legend(loc="best", fontsize=8)
            if self.corrected is not None:
                self.ax_cor.plot(wn, self.corrected[:, i], lw=1.0, color="C2", label=f"corrected {c}")
                self.ax_cor.legend(loc="best", fontsize=8)

        raw_title = "Raw (despiked)" if despiked else "Raw"
        self.ax_raw.set_title(
            raw_title + (" + baseline" if (self.baselines is not None and show_b) else "")
        )
        self.ax_cor.set_title(
            "Baseline-corrected" if self.corrected is not None else "Baseline-corrected (apply first)"
        )
        self._format_axes()
        self.canvas.draw_idle()

    def _format_axes(self) -> None:
        for ax in (self.ax_raw, self.ax_cor):
            ax.set_xlabel("wavenumber (cm$^{-1}$)")
            ax.set_ylabel("intensity")
            ax.grid(True, alpha=0.3)

    def save_corrected(self) -> None:
        if self.corrected is None or self.df is None or self.current_path is None:
            return
        default = self.current_path.with_name(self.current_path.stem + "_corrected.csv")
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save corrected CSV", str(default), "CSV (*.csv)"
        )
        if not path_str:
            return

        wn = self.df["wavenumber"].to_numpy(dtype=float)

        # Mapping input → write back in the same X num/Y num/X,Y,wn pixel-row
        # layout so it stays usable as a 2-D map downstream.
        if self.map_meta is not None:
            try:
                save_corrected_mapping(path_str, wn, self.corrected, self.map_meta)
            except Exception as e:
                QMessageBox.critical(self, "Save error", str(e))
                return
            self.statusBar().showMessage(
                f"Saved mapping {Path(path_str).name}", 6000
            )
            return

        # Non-mapping (TXT stack): wavenumber + spectra columns + summary stats.
        out = pd.DataFrame({"wavenumber": wn})
        for i, c in enumerate(self.spec_cols):
            out[c] = self.corrected[:, i]
        out["mean"] = out[self.spec_cols].mean(axis=1)
        out["sd"] = out[self.spec_cols].std(axis=1, ddof=1)
        try:
            out.to_csv(path_str, index=False)
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))
            return
        self.statusBar().showMessage(f"Saved {Path(path_str).name}", 6000)


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

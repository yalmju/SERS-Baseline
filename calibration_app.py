"""
SERS Calibration — 농도별 스펙트럼 파일을 올리면 검량선과 LOD를 계산하는 창.

화면은 docs/calibration_ui.md + Figma 플러그인 v2 디자인을 따름.
계산은 calibration_core.py, 그래프 스타일은 figstyle.py (Arial 18 pt), 이 파일은 화면만 담당.
실행: python calibration_app.py
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backend_tools import Cursors
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
from PyQt6.QtCore import QByteArray, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QStackedWidget, QStatusBar, QTableWidget, QTableWidgetItem, QTabWidget, QToolButton,
    QVBoxLayout, QWidget,
)

import calibration_core as cc
import figstyle as fs

# ============================================================================ 디자인 토큰 (docs/calibration_ui_tokens.json)
C = dict(
    app="#F4F5F7", surface="#FFFFFF", table_header="#F3F4F6", table_alt="#FAFBFC", hover="#F0F2F5",
    border_card="#E3E6EA", border_control="#D0D4DA", grid="#EEF0F3",
    text="#1F2937", strong="#111827", secondary="#6B7280", toggle="#4B5563", disabled="#A0A6AE",
    accent="#2BA36B", accent_hover="#24905E", accent_disabled="#A9D9C1", accent_subtle="#EAF6F0",
    danger="#C2410C", danger_subtle="#FDF1EA",
)
FILE_FILTER = "Raman data (*.txt *.csv);;All files (*)"
SPECTRA_XRANGE = (400.0, 1800.0)        # 평균 스펙트럼 기본 보기 범위
STATUS_MS = 4000                         # 상태 줄 오른쪽 메시지가 떠 있는 시간
DEBOUNCE_MS = 250                        # 입력이 멈추고 이 시간 뒤 한 번만 다시 계산

STYLESHEET = f"""
QWidget {{ font-family: "Segoe UI", "Malgun Gothic"; font-size: 10pt; color: {C['text']}; }}
QMainWindow, #side, #side > QWidget, #results {{ background: {C['app']}; }}
#card {{ background: {C['surface']}; border: 1px solid {C['border_card']}; border-radius: 10px; }}
#card QLabel {{ background: transparent; }}
#sectionTitle {{ font-size: 11pt; font-weight: 600; }}
#card QLabel#stepBadge {{ background: {C['accent']}; color: white; border-radius: 10px; font-weight: 700;
              min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; }}
#hint, #metricTitle, #metricSub, #detail {{ color: {C['secondary']}; font-size: 9pt; }}
#detail[error="true"] {{ color: {C['danger']}; }}
#metricValue {{ font-size: 15pt; font-weight: 600; color: {C['strong']}; }}
#metricValue[busy="true"], #metricSub[busy="true"] {{ color: {C['disabled']}; }}
#legend {{ color: {C['secondary']}; font-size: 9pt; }}

QPushButton {{ background: {C['surface']}; border: 1px solid {C['border_control']}; border-radius: 6px; padding: 6px 12px; }}
QPushButton:hover {{ background: {C['hover']}; }}
QPushButton:disabled {{ color: {C['disabled']}; }}
QPushButton#primary {{ background: {C['accent']}; color: white; border: none; font-weight: 600; padding: 7px 16px; }}
QPushButton#primary:hover {{ background: {C['accent_hover']}; }}
QPushButton#primary:disabled {{ background: {C['accent_disabled']}; }}
QToolButton#tool {{ border: none; border-radius: 4px; padding: 4px; background: transparent; }}
QToolButton#tool:hover {{ background: {C['hover']}; }}
QToolButton#tool:checked {{ background: {C['accent_subtle']}; }}
QToolButton#toggle {{ border: none; color: {C['toggle']}; font-weight: 600; padding: 2px 0; background: transparent; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ min-height: 20px; }}
QLineEdit, QComboBox {{ background: {C['surface']}; border: 1px solid {C['border_control']}; border-radius: 5px; padding: 2px 6px; }}
QLineEdit[empty="true"] {{ color: {C['disabled']}; background: {C['table_header']}; }}

QTableWidget {{ background: {C['surface']}; border: 1px solid {C['border_card']}; border-radius: 6px;
                gridline-color: {C['grid']}; alternate-background-color: {C['table_alt']}; }}
QTableWidget[drag="true"] {{ border: 2px dashed {C['accent']}; background: {C['accent_subtle']}; }}
QHeaderView::section {{ background: {C['table_header']}; border: none; border-bottom: 1px solid {C['border_card']};
                        padding: 4px 6px; font-weight: 600; color: {C['secondary']}; }}
#dropZone {{ background: {C['surface']}; border: 1px dashed {C['border_control']}; border-radius: 6px; }}
#dropZone[drag="true"] {{ background: {C['accent_subtle']}; border: 2px dashed {C['accent']}; }}
#dropTitle {{ font-weight: 600; }}
#dropTitle[drag="true"] {{ color: {C['accent_hover']}; }}

QTabWidget::pane {{ background: {C['surface']}; border: 1px solid {C['border_card']}; border-radius: 8px;
                    border-top-left-radius: 0; top: -1px; }}
QTabBar::tab {{ padding: 7px 16px; border: 1px solid transparent; color: {C['secondary']}; background: transparent; }}
QTabBar::tab:selected {{ color: {C['strong']}; font-weight: 600; background: {C['surface']};
                         border: 1px solid {C['border_card']}; border-bottom-color: {C['surface']};
                         border-top-left-radius: 6px; border-top-right-radius: 6px; }}
#plotToolbar {{ border: none; border-bottom: 1px solid {C['grid']}; }}
#coords {{ color: {C['secondary']}; font-size: 9pt; }}
QProgressBar#busy {{ border: none; background: {C['grid']}; max-height: 2px; min-height: 2px; }}
QProgressBar#busy::chunk {{ background: {C['accent']}; }}
#placeholderTitle {{ font-size: 11pt; font-weight: 600; color: {C['secondary']}; }}
#placeholderTitle[error="true"] {{ color: {C['danger']}; }}
#placeholderSub {{ color: {C['secondary']}; font-size: 9pt; }}

QStatusBar {{ background: {C['app']}; border-top: 1px solid {C['border_card']}; }}
QStatusBar QLabel {{ color: {C['secondary']}; font-size: 9pt; padding: 0 6px; }}
QSplitter::handle {{ background: {C['border_card']}; }}
QScrollBar:vertical {{ width: 8px; background: transparent; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {C['border_control']}; border-radius: 3px; min-height: 40px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""

# 24 px 격자, 선 굵기 2 (Figma 플러그인 v2 아이콘과 같음)
ICONS = {
    "home": '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
    "zoom": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/><path d="M11 8v6M8 11h6"/>',
    "pan": '<path d="M12 3v18M3 12h18"/><path d="M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3"/>',
    "save": '<path d="M12 4v11M7 10l5 5 5-5"/><path d="M4 17v3h16v-3"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="1"/><path d="M16 8V4H4v12h4"/>',
    "upload": '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 17v3h16v-3"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "check": '<path d="M5 12l5 5 9-10"/>',
    "alert": '<path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17h.01"/>',
    "loader": '<path d="M12 3a9 9 0 1 0 9 9"/>',
}


def icon_pixmap(name: str, color: str = C["toggle"], size: int = 18) -> QPixmap:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')
    ratio = 2
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(svg.encode())).render(p, QRectF(0, 0, size * ratio, size * ratio))
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def icon(name: str, color: str = C["toggle"], size: int = 18) -> QIcon:
    return QIcon(icon_pixmap(name, color, size))


def dot_icon(color: str = C["accent"], d: int = 6) -> QIcon:
    pm = QPixmap(d * 2, d * 2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, d * 2, d * 2)
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


def repolish(w: QWidget, **props) -> None:
    """QSS 동적 속성(busy, error, drag…)을 바꾸고 다시 그림."""
    for k, v in props.items():
        w.setProperty(k, v)
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


# ============================================================================ 그림 (화면·저장 공용, figstyle 규칙)
def _log_axes(ax) -> None:
    """로그축: 10배마다 주눈금, 2-9 보조눈금, 숫자는 0.1, 1, 10 처럼."""
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(LogLocator(base=10, numticks=30))
        axis.set_major_formatter(FuncFormatter(fs._plain))
        axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10), numticks=30))
        axis.set_minor_formatter(NullFormatter())


def draw_calibration(ax, result: "RunResult", fit: cc.Fit | None, color: str = fs.GREEN) -> None:
    loglog = fit is None or fit.kind == "loglog"
    for g in result.groups:
        filled = fit is not None and fit.contains(g.conc)
        ax.errorbar(g.conc, g.mean, g.sd, fmt="s", color=color, mfc=color if filled else "white")
    if fit is not None:
        if loglog:
            xf = np.logspace(np.log10(fit.lo), np.log10(fit.hi), 50)
            ax.plot(xf, 10 ** (fit.intercept + fit.slope * np.log10(xf)), color="k")
        else:
            xf = np.array([fit.lo, fit.hi])
            ax.plot(xf, fit.slope * xf + fit.intercept, color="k")
        ax.text(0.05, 0.95, f"{fit.equation()}\n$R^2$ = {fit.r2:.3f}", transform=ax.transAxes,
                va="top", fontsize=fs.LEGEND_SIZE)
    if result.blank is not None:
        ax.axhline(result.blank.threshold, color=fs.GRAY, ls="--", lw=0.8)
        ax.text(0.98, result.blank.threshold, "blank + 3SD", transform=ax.get_yaxis_transform(),
                ha="right", va="bottom", fontsize=12, color=fs.GRAY)
    c = np.array([g.conc for g in result.groups])
    m = np.array([g.mean for g in result.groups])
    sd = np.nan_to_num(np.array([g.sd for g in result.groups]))
    if loglog:
        ax.set_xscale("log")
        ax.set_yscale("log")
        _log_axes(ax)
        ax.set_xlim(10 ** np.floor(np.log10(c.min())), 10 ** np.ceil(np.log10(c.max()) + 1e-9))
        lows = np.r_[m - sd, m][np.r_[m - sd, m] > 0]
        if len(lows):                     # 데이터가 가운데 오도록 위·아래 반 decade 여유 (식 글자 자리)
            ax.set_ylim(10 ** np.floor(np.log10(lows.min()) - 0.5),
                        10 ** np.ceil(np.log10((m + sd).max()) + 0.5))
    else:
        ax.set_xlim(0, c.max() * 1.1)
        ax.set_ylim(0, (m + sd).max() * 1.35)
    ax.set_xlabel("Concentration (µM)")
    ax.set_ylabel(f"I$_{{{result.settings.peak_center:g}}}$ (a.u.)")


def draw_spectra(ax, result: "RunResult", color: str = fs.GREEN) -> None:
    means = np.array([g.used_spectra.mean(1) for g in result.groups])
    step = 0.8 * max(float(np.median(np.ptp(means, axis=1))), 1.0)
    colors = fs.gradient(len(result.groups), color, light=0.45)
    lo, hi = max(float(result.wn.min()), SPECTRA_XRANGE[0]), min(float(result.wn.max()), SPECTRA_XRANGE[1])
    for i, (g, y, col) in enumerate(zip(result.groups, means, colors)):
        ax.plot(result.wn, y + i * step, color=col)
        ax.text(hi, i * step + float(np.median(y)) + 0.15 * step, cc.format_conc(g.conc),
                color=col, ha="right", va="bottom", fontsize=12)
    c, hw = result.settings.peak_center, result.settings.peak_halfwidth
    ax.axvspan(c - hw, c + hw, color=fs.PINK, alpha=0.15, lw=0)
    ax.set_xlim(lo, hi)
    ax.set_xlabel("Raman shift (cm$^{-1}$)")
    ax.set_ylabel("Intensity (a.u., offset)")
    ax.set_yticks([])
    ax.yaxis.set_tick_params(which="minor", left=False)


def export_figure(fig, path_stem: Path, formats=("pdf", "png", "svg")) -> None:
    """figstyle 규칙대로 저장. 로그축 눈금은 10배마다 모두 표시."""
    fs.tidy(fig)
    for ax in fig.axes:
        if ax.get_xscale() == "log":
            _log_axes(ax)
    fs.fix_legends(fig, verbose=False)
    for ext in formats:
        fig.savefig(path_stem.with_name(f"{path_stem.name}.{ext}"))
    plt.close(fig)


# ============================================================================ 작은 위젯
def _dspin(lo, hi, val, decimals, step, tip="") -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setValue(val)
    s.setSingleStep(step)
    s.setToolTip(tip)
    return s


def _ispin(lo, hi, val, step=1, tip="") -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(val)
    s.setSingleStep(step)
    s.setToolTip(tip)
    return s


def _check(text, on=True, tip="") -> QCheckBox:
    c = QCheckBox(text)
    c.setChecked(on)
    c.setToolTip(tip)
    return c


def _label(text, name, wrap=False) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def _form(rows) -> QFormLayout:
    f = QFormLayout()
    f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    f.setHorizontalSpacing(12)
    f.setVerticalSpacing(8)
    for label, w in rows:
        if label is None:
            f.addRow(w)
        else:
            f.addRow(label, w)
    return f


class Section(QFrame):
    """번호가 붙은 흰 카드 (SectionHeader + 본문)."""

    def __init__(self, step: str, title: str) -> None:
        super().__init__()
        self.setObjectName("card")
        badge = _label(step, "stepBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(badge)
        top.addWidget(_label(title, "sectionTitle"), 1)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(8)
        lay.addLayout(top)
        lay.addLayout(self.body)


class Collapsible(QWidget):
    """제목을 누르면 펼쳐지는 영역 (Baseline and smoothing)."""

    def __init__(self, title: str, content: QWidget) -> None:
        super().__init__()
        self.btn = QToolButton()
        self.btn.setObjectName("toggle")
        self.btn.setText(title)
        self.btn.setCheckable(True)
        self.btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn.setIcon(icon("chevron-right", C["toggle"], 14))
        self.btn.toggled.connect(self._toggle)
        self.content = content
        content.setVisible(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.btn)
        lay.addWidget(content)

    def _toggle(self, on: bool) -> None:
        self.btn.setIcon(icon("chevron-down" if on else "chevron-right", C["toggle"], 14))
        self.content.setVisible(on)


class MetricCard(QFrame):
    """결과 카드: 제목 / 값 / 보조 줄. busy = 계산 중이라 이전 값을 회색으로."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setFixedHeight(85)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.value = _label("–", "metricValue")
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.sub = _label(" ", "metricSub")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        lay.addWidget(_label(title, "metricTitle"))
        lay.addWidget(self.value)
        lay.addWidget(self.sub)

    def set(self, value: str, sub: str = " ") -> None:
        self.value.setText(value)
        self.sub.setText(sub or " ")

    def set_busy(self, busy: bool) -> None:
        repolish(self.value, busy=busy)
        repolish(self.sub, busy=busy)


def _drop_paths(event) -> list[str]:
    return [u.toLocalFile() for u in event.mimeData().urls()
            if u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in (".txt", ".csv")]


class DropZone(QFrame):
    """파일이 하나도 없을 때 보이는 끌어다 놓기 영역."""
    filesDropped = pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(200)
        self.ico = QLabel()
        self.title = _label("", "dropTitle")
        self.sub = _label("", "hint")
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        for w in (self.ico, self.title, self.sub):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            w.setStyleSheet("background: transparent; border: none;")
            lay.addWidget(w)
        lay.addStretch(1)
        self.set_drag(0)

    def set_drag(self, n: int) -> None:
        on = n > 0
        self.ico.setPixmap(icon_pixmap("upload", C["accent"] if on else C["secondary"], 22))
        self.title.setText(f"Release to add {n} file{'s' if n != 1 else ''}" if on else "Drop spectra files here")
        self.sub.setText("Concentrations are read from the file names" if on else "or use Add files…  ·  .txt, .csv")
        repolish(self, drag=on)
        repolish(self.title, drag=on)

    def dragEnterEvent(self, e):
        paths = _drop_paths(e)
        if paths:
            self.set_drag(len(paths))
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.set_drag(0)

    def dropEvent(self, e):
        paths = _drop_paths(e)
        self.set_drag(0)
        if paths:
            self.filesDropped.emit(paths)
            e.acceptProposedAction()


class FileTable(QTableWidget):
    """File · Spectra · Conc (µM). 파일을 끌어다 놓을 수 있음."""
    filesDropped = pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__(0, 3)
        self.setHorizontalHeaderLabels(["File", "Spectra", "Conc (µM)"])
        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(1, 62)
        self.setColumnWidth(2, 92)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)     # 농도는 보통 이름 앞쪽에 있음 (전체 이름은 툴팁)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setMinimumHeight(200)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    def set_drag(self, on: bool) -> None:
        repolish(self, drag=on)

    def dragEnterEvent(self, e):
        if _drop_paths(e):
            self.set_drag(True)
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if _drop_paths(e):
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.set_drag(False)

    def dropEvent(self, e):
        paths = _drop_paths(e)
        self.set_drag(False)
        if paths:
            self.filesDropped.emit(paths)
            e.acceptProposedAction()


class PlotPanel(QWidget):
    """툴바 (Reset view · Zoom · Pan │ Save figure · Copy · 좌표) + 진행 막대 + 그래프 / 안내 화면."""

    def __init__(self, square: bool, coord_fmt, on_save, on_copy) -> None:
        super().__init__()
        self.fig = Figure(layout="constrained")
        self.ax = self.fig.add_subplot(111)
        self.square = square
        self.canvas = FigureCanvas(self.fig)
        self.nav = NavigationToolbar2QT(self.canvas, self)      # 확대·이동 기능만 빌려 쓰고 숨김
        self.nav.hide()
        self.coord_fmt = coord_fmt

        bar = QFrame()
        bar.setObjectName("plotToolbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(2)
        self.btn_home = self._tool("home", "Reset view", self.nav.home)
        self.btn_zoom = self._tool("zoom", "Zoom (drag a box)", self._zoom, checkable=True)
        self.btn_pan = self._tool("pan", "Pan", self._pan, checkable=True)
        sep = QFrame()
        sep.setFixedSize(1, 18)
        sep.setStyleSheet(f"background: {C['border_card']}; border: none;")
        self.btn_save = self._tool("save", "Save figure (PDF, PNG, SVG · figstyle)", on_save)
        self.btn_copy = self._tool("copy", "Copy figure to clipboard", lambda: on_copy(self.canvas))
        for w in (self.btn_home, self.btn_zoom, self.btn_pan, sep, self.btn_save, self.btn_copy):
            row.addWidget(w)
        row.addStretch(1)
        self.coords = _label("", "coords")
        row.addWidget(self.coords)

        self.busy = QProgressBar()
        self.busy.setObjectName("busy")
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.setVisible(False)

        self.place = QWidget()
        pv = QVBoxLayout(self.place)
        pv.addStretch(1)
        self.place_icon = QLabel()
        self.place_title = _label("", "placeholderTitle")
        self.place_sub = _label("", "placeholderSub")
        for w in (self.place_icon, self.place_title, self.place_sub):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pv.addWidget(w)
        pv.addStretch(1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.place)
        self.stack.addWidget(self.canvas)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(bar)
        lay.addWidget(self.busy)
        lay.addWidget(self.stack, 1)
        self.canvas.mpl_connect("motion_notify_event", self._on_move)
        self.show_placeholder(error=False)

    def _tool(self, name, tip, slot, checkable=False) -> QToolButton:
        b = QToolButton()
        b.setObjectName("tool")
        b.setIcon(icon(name))
        b.setIconSize(QSize(18, 18))
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.clicked.connect(lambda *_: slot())
        return b

    def _sync_mode(self) -> None:
        mode = str(self.nav.mode)
        self.btn_zoom.setChecked("zoom" in mode)
        self.btn_pan.setChecked("pan" in mode)

    def _zoom(self) -> None:
        self.nav.zoom()
        self._sync_mode()

    def _pan(self) -> None:
        self.nav.pan()
        self._sync_mode()

    def _on_move(self, e) -> None:
        if e.inaxes is self.ax and e.xdata is not None and e.ydata is not None:
            self.coords.setText(self.coord_fmt(e.xdata, e.ydata))
        else:
            self.coords.setText("")

    @property
    def tool_active(self) -> bool:
        return bool(str(self.nav.mode))

    def _enable_tools(self, on: bool) -> None:
        for b in (self.btn_home, self.btn_zoom, self.btn_pan, self.btn_save, self.btn_copy):
            b.setEnabled(on)

    def show_placeholder(self, error: bool) -> None:
        self.place_icon.setPixmap(icon_pixmap("alert" if error else "upload",
                                              C["danger"] if error else C["disabled"], 28))
        self.place_title.setText("Check the settings on the left" if error
                                 else "Drop spectra files on the left to start")
        self.place_sub.setText("The plot comes back as soon as every value is valid." if error
                               else "Results appear here once there are two or more concentrations.")
        repolish(self.place_title, error=error)
        self.stack.setCurrentWidget(self.place)
        self._enable_tools(False)
        self.coords.setText("")

    def redraw(self, draw) -> None:
        self.ax.clear()
        if self.square:
            self.ax.set_box_aspect(1)
        draw(self.ax)
        self.stack.setCurrentWidget(self.canvas)
        self._enable_tools(True)
        self.canvas.draw_idle()


@dataclass
class RunResult:
    """계산 한 번의 입력과 결과. 그래프·저장은 화면 값이 아니라 항상 이것을 씀."""
    settings: cc.Settings
    wn: np.ndarray
    groups: list[cc.Group]
    blank: cc.Blank | None


# ============================================================================ 메인 창
ROLE_PATH = Qt.ItemDataRole.UserRole          # File 칸: 전체 경로
ROLE_PARSED = Qt.ItemDataRole.UserRole + 1    # Conc 칸: 파일 이름에서 읽은 값 (손으로 고쳤는지 비교용)


class CalibrationWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        fs.use()                   # 그래프 규칙(yalmjufigurestyle): Arial 18 pt, 바깥 눈금, L자 축
        self.setWindowTitle("SERS Calibration")
        self.resize(1400, 880)
        self.result: RunResult | None = None
        self.fit: cc.Fit | None = None
        self.message: str | None = None          # 마지막 계산 오류 (없으면 None)
        self.manual_range: tuple[float, float] | None = None   # 직접 정한 구간 (µM, 칸의 반올림 없이)
        self._hand = False                        # 검량선 점 위에서 손가락 커서인지
        self.blank_files: list[Path] = []
        self.unreadable: dict[str, str] = {}     # 경로 → 읽지 못한 이유
        self.cache = cc.SpectraCache()           # 전처리 결과 저장 → 피크·희석·제외 변경은 즉시 반영
        self.last_dir = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self.recompute)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self.lbl_flash.setText(""))

        side = QWidget()
        side.setObjectName("side")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(14, 14, 10, 14)
        sv.setSpacing(12)
        for build in (self._build_samples, self._build_blank, self._build_processing, self._build_fit):
            sv.addWidget(build())
        sv.addStretch(1)
        scroll = QScrollArea()
        scroll.setObjectName("side")
        scroll.setWidget(side)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(440)
        self.side_scroll = scroll

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(1)
        split.addWidget(scroll)
        split.addWidget(self._build_results())
        split.setStretchFactor(1, 1)
        split.setSizes([440, 960])
        self.setCentralWidget(split)

        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.lbl_summary = QLabel("No files")
        self.lbl_flash = QLabel("")
        sb.addWidget(self.lbl_summary, 1)
        sb.addPermanentWidget(self.lbl_flash)
        self.setStatusBar(sb)

        self._auto_toggled(True)
        self._refresh_file_widgets()
        self._show_empty()

    # ------------------------------------------------------------------ 왼쪽 단계
    def _build_samples(self) -> Section:
        sec = Section("1", "Sample spectra")
        self.drop_zone = DropZone()
        self.drop_zone.filesDropped.connect(self._add_paths)
        self.tbl_files = FileTable()
        self.tbl_files.filesDropped.connect(self._add_paths)
        self.tbl_files.itemChanged.connect(self._conc_edited)
        self.files_stack = QStackedWidget()
        self.files_stack.addWidget(self.drop_zone)
        self.files_stack.addWidget(self.tbl_files)

        row = QHBoxLayout()
        row.setSpacing(6)
        b_add = QPushButton("Add files…")
        b_add.setIcon(icon("upload"))
        b_add.clicked.connect(self.add_files)
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.clicked.connect(self.remove_files)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_files)
        for b in (b_add, self.btn_remove, self.btn_clear):
            row.addWidget(b)
        row.addStretch(1)
        self.lbl_edited = _label(f"<span style='color:{C['accent']}'>●</span> edited by hand", "legend")
        row.addWidget(self.lbl_edited)

        sec.body.addWidget(_label("Drop .txt / .csv files below. Concentration is read from the file name "
                                  "(100nM, 2-5uM, 1 mM) — click a value to change it.", "hint", wrap=True))
        sec.body.addWidget(self.files_stack)
        sec.body.addLayout(row)
        return sec

    def _build_blank(self) -> Section:
        sec = Section("2", "Blank (no analyte)")
        self.edt_blank = QLineEdit()
        self.edt_blank.setReadOnly(True)
        self.edt_blank.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b = QPushButton("Choose blank…")
        b.clicked.connect(self.add_blank)
        self.btn_blank_clear = QPushButton("Clear")
        self.btn_blank_clear.clicked.connect(self.clear_blank)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.edt_blank, 1)
        row.addWidget(b)
        row.addWidget(self.btn_blank_clear)
        sec.body.addLayout(row)
        sec.body.addWidget(_label("Use the raw file — it is processed with the same settings as the samples.",
                                  "hint", wrap=True))
        self._refresh_blank_widgets()
        return sec

    def _build_processing(self) -> Section:
        d = cc.Settings()
        self.spn_dil = _dspin(0.0001, 1e6, d.dilution, 4, 0.5,
                              "File-name concentration × this = actual concentration (0.5 for a 1:1 dilution)")
        self.spn_center = _dspin(100, 4000, d.peak_center, 1, 1,
                                 "Peak used for the calibration. Tip: click a peak in Mean spectra.")
        self.spn_hw = _dspin(3, 200, d.peak_halfwidth, 1, 0.5, "Peak window = center ± this")
        self.chk_trim = _check("Exclude highest and lowest spectrum per concentration", d.trim,
                               "Also applied to the blank. Skipped when a concentration has fewer than 4 spectra.")
        self.chk_despike = _check("Remove spikes", d.despike)
        self.spn_sw = _ispin(0, 51, d.smooth_window, 2, "Savitzky–Golay window (points, odd). 0 = off")
        self.spn_so = _ispin(1, 5, d.smooth_order)
        self.cmb_algo = QComboBox()
        self.cmb_algo.addItems(["ALS", "airPLS"])
        self.spn_lam = _dspin(1e2, 1e10, d.lam, 0, 1e4)
        self.spn_p = _dspin(1e-4, 0.5, d.p, 4, 0.005)
        self.spn_iter = _ispin(5, 500, d.max_iter)
        self.cmb_algo.currentTextChanged.connect(lambda t: self.spn_p.setEnabled(t == "ALS"))
        for w in (self.spn_dil, self.spn_center, self.spn_hw, self.spn_sw, self.spn_so,
                  self.spn_lam, self.spn_p, self.spn_iter):
            w.valueChanged.connect(self._schedule)
        for w in (self.chk_trim, self.chk_despike):
            w.toggled.connect(self._schedule)
        self.cmb_algo.currentTextChanged.connect(self._schedule)

        adv = QWidget()
        adv.setLayout(_form([("Smoothing window", self.spn_sw), ("Smoothing order", self.spn_so),
                             ("Baseline", self.cmb_algo), ("λ", self.spn_lam), ("p", self.spn_p),
                             ("Max iterations", self.spn_iter)]))
        adv.layout().setContentsMargins(0, 4, 0, 0)

        sec = Section("3", "Processing")
        sec.body.addLayout(_form([("Dilution factor", self.spn_dil), ("Peak center (cm⁻¹)", self.spn_center),
                                  ("Window ± (cm⁻¹)", self.spn_hw)]))
        sec.body.addWidget(self.chk_trim)
        sec.body.addWidget(self.chk_despike)
        self.collapsible = Collapsible("Baseline and smoothing", adv)
        sec.body.addWidget(self.collapsible)
        return sec

    def _build_fit(self) -> Section:
        self.cmb_fit = QComboBox()
        self.cmb_fit.addItems(["log-log", "Linear (y = ax + b)"])
        self.chk_auto = _check("Automatic range", tip="From the first concentration above blank + 3SD "
                                                      "to the concentration with the highest intensity")
        self.spn_lo = _dspin(1e-6, 1e6, 0.5, 4, 0.1)
        self.spn_hi = _dspin(1e-6, 1e6, 25, 4, 1)
        self.spn_mw = _dspin(0, 5000, 0, 2, 1, "Molecular weight. Shows the LOD in mg/L too. 0 = off")
        self.cmb_fit.currentIndexChanged.connect(self.refit)
        self.chk_auto.toggled.connect(self._auto_toggled)
        for w in (self.spn_lo, self.spn_hi):
            w.valueChanged.connect(self._range_typed)
        self.spn_mw.valueChanged.connect(self.refit)
        rng = QHBoxLayout()
        rng.setContentsMargins(0, 0, 0, 0)
        rng.addWidget(self.spn_lo, 1)
        rng.addWidget(QLabel("–"))
        rng.addWidget(self.spn_hi, 1)
        rng_w = QWidget()
        rng_w.setLayout(rng)

        sec = Section("4", "Fit")
        sec.body.addLayout(_form([("Model", self.cmb_fit), (None, self.chk_auto),
                                  ("Range (µM)", rng_w), ("MW (g/mol)", self.spn_mw)]))
        sec.body.addWidget(_label("Or click a point on the calibration curve: a point outside the range "
                                  "extends it, an end point is dropped, a point inside becomes the nearer end.",
                                  "hint", wrap=True))
        return sec

    # ------------------------------------------------------------------ 오른쪽 결과
    def _build_results(self) -> QWidget:
        self.card_eq = MetricCard("Calibration")
        self.card_r2 = MetricCard("R²")
        self.card_lod = MetricCard("LOD")
        self.card_rng = MetricCard("Fitted range")
        cards = QGridLayout()
        cards.setSpacing(10)
        for i, (card, stretch) in enumerate(((self.card_eq, 3), (self.card_r2, 1),
                                             (self.card_lod, 2), (self.card_rng, 2))):
            cards.addWidget(card, 0, i)
            cards.setColumnStretch(i, stretch)

        self.detail_icon = QLabel()
        self.lbl_detail = _label("", "detail")
        self.lbl_detail.setTextFormat(Qt.TextFormat.PlainText)
        detail = QHBoxLayout()
        detail.setSpacing(6)
        detail.addWidget(self.detail_icon)
        detail.addWidget(self.lbl_detail, 1)

        self.panel_cal = PlotPanel(True, lambda x, y: f"x = {x:.3g} µM    y = {y:,.0f} a.u.".replace(",", " "),
                                   lambda: self.save_figure("calibration"), self.copy_figure)
        self.panel_spec = PlotPanel(False, lambda x, y: f"x = {x:,.1f} cm⁻¹    y = {y:,.0f} a.u.".replace(",", " "),
                                    lambda: self.save_figure("spectra"), self.copy_figure)
        self.panel_spec.canvas.mpl_connect("button_press_event", self._pick_peak)
        self.panel_cal.canvas.mpl_connect("button_press_event", self._click_point)
        self.panel_cal.canvas.mpl_connect("motion_notify_event", self._hover_point)
        self.tbl_sum = QTableWidget(0, 7)
        self.tbl_sum.setHorizontalHeaderLabels(["Conc", "n used / total", "Mean", "SD", "RSD (%)", "In fit", "Files"])
        self.tbl_sum.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.tbl_sum.verticalHeader().setVisible(False)
        self.tbl_sum.setAlternatingRowColors(True)
        self.tbl_sum.setShowGrid(False)
        self.tbl_sum.setWordWrap(False)
        self.tbl_sum.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.tbl_sum.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table_page = QWidget()
        tv = QVBoxLayout(table_page)
        tv.setContentsMargins(12, 12, 12, 12)
        tv.addWidget(self.tbl_sum)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.panel_cal, "Calibration curve")
        self.tabs.addTab(self.panel_spec, "Mean spectra")
        self.tabs.addTab(table_page, "Summary table")
        self.btn_export = QPushButton("Export results…")
        self.btn_export.setObjectName("primary")
        self.btn_export.setIcon(icon("save", "#FFFFFF"))
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export)
        corner = QWidget()
        cl = QHBoxLayout(corner)
        cl.setContentsMargins(0, 0, 0, 5)
        cl.addWidget(self.btn_export)
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)

        right = QWidget()
        right.setObjectName("results")
        v = QVBoxLayout(right)
        v.setContentsMargins(10, 14, 14, 14)
        v.setSpacing(10)
        v.addLayout(cards)
        v.addLayout(detail)
        v.addWidget(self.tabs, 1)
        return right

    # ------------------------------------------------------------------ 상태 표시
    def flash(self, text: str) -> None:
        """상태 줄 오른쪽에 잠깐 띄우는 메시지."""
        self.lbl_flash.setText(text)
        self._flash_timer.start(STATUS_MS)

    def _set_detail(self, text: str, kind: str = "info") -> None:
        """카드 아래 한 줄. kind: info / error / busy"""
        names = {"error": ("alert", C["danger"]), "busy": ("loader", C["accent"])}
        if kind in names:
            self.detail_icon.setPixmap(icon_pixmap(names[kind][0], names[kind][1], 14))
            self.detail_icon.show()
        else:
            self.detail_icon.hide()
        self.lbl_detail.setText(text)
        repolish(self.lbl_detail, error=(kind == "error"))

    # ------------------------------------------------------------------ 입력
    def settings(self) -> cc.Settings:
        return cc.Settings(
            despike=self.chk_despike.isChecked(), algo=self.cmb_algo.currentText(),
            lam=self.spn_lam.value(), p=self.spn_p.value(), max_iter=self.spn_iter.value(),
            smooth_window=self.spn_sw.value(), smooth_order=self.spn_so.value(),
            peak_center=self.spn_center.value(), peak_halfwidth=self.spn_hw.value(),
            trim=self.chk_trim.isChecked(), dilution=self.spn_dil.value())

    def _rows(self) -> list[tuple[int, str, str]]:
        """(행 번호, 경로, Conc 칸 글자)"""
        out = []
        for r in range(self.tbl_files.rowCount()):
            conc = self.tbl_files.item(r, 2)
            out.append((r, self.tbl_files.item(r, 0).data(ROLE_PATH), (conc.text() if conc else "").strip()))
        return out

    @staticmethod
    def _parse_conc(text: str) -> float | None:
        try:
            v = float(text)
        except ValueError:
            return None
        return v if v > 0 and np.isfinite(v) else None

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Sample spectra", self.last_dir, FILE_FILTER)
        self._add_paths(paths)

    def _add_paths(self, paths: list[str]) -> None:
        existing = {p for _, p, _ in self._rows()}
        self.tbl_files.blockSignals(True)
        added = 0
        for p in paths:
            if p in existing or Path(p).suffix.lower() not in (".txt", ".csv"):
                continue
            r = self.tbl_files.rowCount()
            self.tbl_files.insertRow(r)
            name = QTableWidgetItem(Path(p).name)
            name.setData(ROLE_PATH, p)
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name.setToolTip(p)
            spectra = QTableWidgetItem("")
            spectra.setFlags(spectra.flags() & ~Qt.ItemFlag.ItemIsEditable)
            spectra.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            c = cc.parse_concentration(Path(p).name)
            conc = QTableWidgetItem("" if c is None else f"{c:g}")
            conc.setData(ROLE_PARSED, "" if c is None else f"{c:g}")
            conc.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for col, item in enumerate((name, spectra, conc)):
                self.tbl_files.setItem(r, col, item)
            added += 1
        self.tbl_files.sortItems(0)
        self.tbl_files.blockSignals(False)
        if paths:
            self.last_dir = str(Path(paths[0]).parent)
        if added:
            self.flash(f"Added {added} file{'s' if added != 1 else ''}")
        self._refresh_file_widgets()
        self._schedule()

    def remove_files(self) -> None:
        for r in sorted({i.row() for i in self.tbl_files.selectedIndexes()}, reverse=True):
            self.tbl_files.removeRow(r)
        self._refresh_file_widgets()
        self._schedule()

    def clear_files(self) -> None:
        self.tbl_files.setRowCount(0)
        self._refresh_file_widgets()
        self._schedule()

    def _conc_edited(self, item: QTableWidgetItem) -> None:
        if item.column() == 2:
            self._refresh_file_widgets()
            self._schedule()

    def add_blank(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Blank spectra (no analyte)", self.last_dir, FILE_FILTER)
        if paths:
            self.blank_files = [Path(p) for p in paths]
            self._refresh_blank_widgets()
            self._schedule()

    def clear_blank(self) -> None:
        self.blank_files = []
        self._refresh_blank_widgets()
        self._schedule()

    def _refresh_blank_widgets(self, n_spectra: int | None = None) -> None:
        if self.blank_files:
            names = ", ".join(p.name for p in self.blank_files)
            self.edt_blank.setText(names + (f"  ·  {n_spectra} spectra" if n_spectra else ""))
        else:
            self.edt_blank.setText("No blank chosen — LOD is not calculated")
        self.edt_blank.setCursorPosition(0)
        self.edt_blank.setToolTip(self.edt_blank.text())
        repolish(self.edt_blank, empty=not self.blank_files)
        self.btn_blank_clear.setEnabled(bool(self.blank_files))

    def _refresh_file_widgets(self, counts: dict[str, int] | None = None) -> None:
        """파일 표 모양: 스펙트럼 개수, 손으로 고친 농도(초록 점), 잘못된 농도(빨강), 못 읽은 파일(빨간 줄)."""
        counts = counts or {}
        rows = self._rows()
        self.files_stack.setCurrentWidget(self.tbl_files if rows else self.drop_zone)
        self.btn_remove.setEnabled(bool(rows))
        self.btn_clear.setEnabled(bool(rows))
        edited_any = False
        self.tbl_files.blockSignals(True)
        for r, path, text in rows:
            f_item, s_item, c_item = (self.tbl_files.item(r, k) for k in range(3))
            bad_file = path in self.unreadable
            bad_conc = self._parse_conc(text) is None
            edited = not bad_conc and text != (c_item.data(ROLE_PARSED) or "")
            edited_any |= edited
            f_item.setText(Path(path).name + (f" — {self.unreadable[path]}" if bad_file else ""))
            f_item.setIcon(icon("alert", C["danger"], 14) if bad_file else QIcon())
            f_item.setForeground(QColor(C["danger"] if bad_file else C["text"]))
            if bad_file:
                s_item.setText("—")
            elif path in counts:
                s_item.setText(str(counts[path]))
            s_item.setForeground(QColor(C["secondary"]))
            c_item.setIcon(dot_icon() if edited else QIcon())
            c_item.setForeground(QColor(C["danger"] if bad_conc else C["text"]))
            for item, red in ((f_item, bad_file), (s_item, bad_file), (c_item, bad_file or bad_conc)):
                if red:
                    item.setBackground(QColor(C["danger_subtle"]))
                else:
                    item.setData(Qt.ItemDataRole.BackgroundRole, None)
        self.tbl_files.blockSignals(False)
        self.lbl_edited.setVisible(edited_any)

    # ------------------------------------------------------------------ 계산
    def _schedule(self, *_) -> None:
        """입력이 바뀔 때마다 호출. 연달아 바뀌면 마지막 한 번만 계산."""
        self._timer.start()

    def recompute(self) -> None:
        """파일·설정이 바뀌면 자동으로 다시 계산. 같은 전처리 결과는 cache에서 꺼냄."""
        self.message = None
        rows = self._rows()
        if not rows:
            self.result, self.fit, self.unreadable = None, None, {}
            self._show_empty()
            return
        s = self.settings()
        bad = [(r, t) for r, _, t in rows if self._parse_conc(t) is None]
        if bad:
            r, t = bad[0]
            why = (f'Conc (µM) in row {r + 1} is "{t}" — use a dot as the decimal separator.' if "," in t
                   else f"Conc (µM) in row {r + 1} is empty — type the concentration in µM." if not t
                   else f'Conc (µM) in row {r + 1} is "{t}" — enter a positive number in µM.')
            self._show_error(why)
            return
        paths = [p for _, p, _ in rows] + [str(p) for p in self.blank_files]
        busy = not all(self.cache.has(p, s) for p in paths)
        if busy:
            self._set_busy(True, "Calculating… re-processing spectra")
        try:
            counts, self.unreadable = {}, {}
            for _, p, _ in rows:                              # 파일별로 읽어 개수·오류를 표에 표시
                try:
                    counts[p] = self.cache.get(p, s)[1].shape[1]
                except Exception as e:
                    self.unreadable[p] = str(e).split(": ", 1)[-1]
            self._refresh_file_widgets(counts)
            files = [(p, self._parse_conc(t)) for _, p, t in rows if p not in self.unreadable]
            if not files:
                raise ValueError("None of the files could be read — see the red rows.")
            wn, groups = cc.process_groups(files, s, cache=self.cache)
            blank = cc.blank_threshold(self.blank_files, s, cache=self.cache) if self.blank_files else None
        except Exception as e:
            self._show_error(str(e))
            return
        finally:
            if busy:
                self._set_busy(False)
        self.result = RunResult(s, wn, groups, blank)
        if blank is not None:                                  # 파일에 든 원래 개수 (제외 전)
            self._refresh_blank_widgets(sum(self.cache.get(p, s)[1].shape[1] for p in self.blank_files))
        n = len(files)
        self.lbl_summary.setText(f"{n} file{'s' if n != 1 else ''} · {len(groups)} concentrations")
        if self.unreadable:
            self.flash(f"{len(self.unreadable)} file(s) could not be read — see the red rows")
        self.refit()

    def _set_busy(self, busy: bool, text: str = "") -> None:
        for card in (self.card_eq, self.card_r2, self.card_lod, self.card_rng):
            card.set_busy(busy)
        for panel in (self.panel_cal, self.panel_spec):
            panel.busy.setVisible(busy)
        if busy:
            self._set_detail(text, "busy")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
        else:
            QApplication.restoreOverrideCursor()

    def _show_empty(self) -> None:
        self._reset_cards()
        self._set_detail("No result yet — add at least two concentrations.")
        self.lbl_summary.setText("No files")
        self._redraw()

    def _show_error(self, text: str) -> None:
        self.result, self.fit, self.message = None, None, text
        self._reset_cards()
        self._set_detail(text, "error")
        self._redraw()

    def _reset_cards(self) -> None:
        for card in (self.card_eq, self.card_r2, self.card_lod, self.card_rng):
            card.set("–")
        self.btn_export.setEnabled(False)

    def _auto_toggled(self, on: bool) -> None:
        self.spn_lo.setEnabled(not on)
        self.spn_hi.setEnabled(not on)
        if not on:                               # 자동 구간에서 이어서 시작 (칸의 반올림 없이)
            self.manual_range = ((self.fit.lo, self.fit.hi) if self.fit is not None
                                 else (self.spn_lo.value(), self.spn_hi.value()))
        self.refit()

    def _range_typed(self) -> None:
        self.manual_range = (self.spn_lo.value(), self.spn_hi.value())
        self.refit()

    def _sync_range_boxes(self, lo: float, hi: float) -> None:
        for w, v in ((self.spn_lo, lo), (self.spn_hi, hi)):
            w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(False)

    def _fit_range(self) -> tuple[float, float]:
        if not self.chk_auto.isChecked():
            if self.manual_range is None:
                self.manual_range = (self.spn_lo.value(), self.spn_hi.value())
            return self.manual_range
        g, b = self.result.groups, self.result.blank
        lo, hi = cc.auto_range(np.array([x.conc for x in g]), np.array([x.mean for x in g]),
                               None if b is None else b.threshold)
        self._sync_range_boxes(lo, hi)
        return lo, hi

    # ------------------------------------------------------------------ 검량선 점 클릭 → 구간
    def _point_at(self, event) -> int | None:
        """커서 아래 농도 점의 번호 (농도 오름차순). 마커 14 px 안 또는 오차 막대 위."""
        if (self.result is None or event.inaxes is not self.panel_cal.ax or event.x is None
                or self.panel_cal.tool_active):
            return None
        ax = self.panel_cal.ax
        tol = 14 * self.panel_cal.canvas.device_pixel_ratio
        best, best_d = None, np.inf
        for i, g in enumerate(self.result.groups):
            if not (np.isfinite(g.mean) and g.conc > 0 and (g.mean > 0 or ax.get_yscale() != "log")):
                continue
            px, py = ax.transData.transform((g.conc, g.mean))
            d = float(np.hypot(event.x - px, event.y - py))
            sd = float(np.nan_to_num(g.sd))
            if d > tol and sd > 0 and abs(event.x - px) <= tol / 2:      # 오차 막대 위
                y0 = ax.transData.transform((g.conc, max(g.mean - sd, g.mean * 1e-3)))[1]
                y1 = ax.transData.transform((g.conc, g.mean + sd))[1]
                if y0 - tol / 2 <= event.y <= y1 + tol / 2:
                    d = abs(event.x - px)
            if d <= tol and d < best_d:
                best, best_d = i, d
        return best

    def _current_span(self) -> tuple[float, float]:
        if self.fit is not None:
            return self.fit.lo, self.fit.hi
        return self.manual_range or (self.spn_lo.value(), self.spn_hi.value())

    def _range_after_click(self, i: int) -> tuple[float, float] | None:
        """클릭한 점으로 바뀔 구간. 바꿀 수 없으면 None (점이 2개보다 적어짐)."""
        c = [g.conc for g in self.result.groups]
        lo, hi = self._current_span()
        inside = [k for k, x in enumerate(c) if cc.in_range(x, lo, hi)]
        if not inside:                                   # 구간에 점이 없음 → 이 점부터 다시
            return c[i], c[i]
        first, last = inside[0], inside[-1]
        if i < first:
            return c[i], c[last]
        if i > last:
            return c[first], c[i]
        if last - first < 2:                             # 점 2개만 남음 → 더 뺄 수 없음
            return None
        if i == first:
            return c[first + 1], c[last]
        if i == last:
            return c[first], c[last - 1]
        return (c[i], c[last]) if i - first <= last - i else (c[first], c[i])

    def _click_point(self, event) -> None:
        if event.button != 1 or event.dblclick:
            return
        i = self._point_at(event)
        if i is None:
            return
        new = self._range_after_click(i)
        if new is None:
            self.flash("The fit needs at least 2 concentrations")
            return
        self.manual_range = new
        self._sync_range_boxes(*new)
        if self.chk_auto.isChecked():
            self.chk_auto.blockSignals(True)
            self.chk_auto.setChecked(False)
            self.chk_auto.blockSignals(False)
            self.spn_lo.setEnabled(True)
            self.spn_hi.setEnabled(True)
        self.refit()
        self.flash(f"Fit range {cc.format_conc(new[0])} – {cc.format_conc(new[1])}")

    def _hover_point(self, event) -> None:
        """점 위에서 손가락 커서 + 클릭하면 무엇이 되는지 좌표 칸에 표시."""
        if self.panel_cal.tool_active:
            return
        i = self._point_at(event)
        canvas = self.panel_cal.canvas
        if i is None:
            if self._hand:
                canvas.set_cursor(Cursors.POINTER)
                self._hand = False
            return
        canvas.set_cursor(Cursors.HAND)
        self._hand = True
        g = self.result.groups[i]
        lo, hi = self._current_span()
        new = self._range_after_click(i)
        if new is None:
            what = "at least 2 concentrations needed"
        elif cc.in_range(g.conc, *new) and not cc.in_range(g.conc, lo, hi):
            what = "click to include"
        elif not cc.in_range(g.conc, *new):
            what = "click to exclude"
        else:
            what = "click to start the fit here" if new[0] == g.conc else "click to end the fit here"
        self.panel_cal.coords.setText(f"{cc.format_conc(g.conc)}    {what}")

    def refit(self) -> None:
        if self.result is None:
            return
        kind = "loglog" if self.cmb_fit.currentIndex() == 0 else "linear"
        try:
            self.fit = cc.fit_curve(self.result.groups, kind, *self._fit_range(), self.result.blank)
        except Exception as e:
            self.fit = None
            self._reset_cards()
            self._set_detail(f"Fit failed: {e}", "error")
            self._redraw()
            return
        self._show_metrics()
        self.btn_export.setEnabled(True)
        self._redraw()

    def _show_metrics(self) -> None:
        f, b, mw = self.fit, self.result.blank, self.spn_mw.value()
        self.card_eq.set(f.equation(), "C in µM")
        self.card_r2.set(f"{f.r2:.4f}")
        if f.lod is None:
            self.card_lod.set("–", f.lod_note)
        else:
            parts = [f"{f.lod * mw / 1000:.3g} mg/L"] if mw > 0 else []
            parts.append(f"blank + 3SD = {b.threshold:.1f}" if f.kind == "loglog" else "3 SD(blank) / slope")
            self.card_lod.set(cc.format_conc(f.lod), "  ·  ".join(parts))
        n_in = sum(f.contains(g.conc) for g in self.result.groups)
        self.card_rng.set(f"{cc.format_conc(f.lo)} – {cc.format_conc(f.hi)}", f"{n_in} concentrations")
        if b is None:
            self._set_detail("No blank — LOD is not calculated. Choose a blank file in step 2.")
        else:
            self._set_detail(f"Blank {b.mean:.1f} ± {b.sd:.1f} (n = {b.n}), mean + 3SD = {b.threshold:.1f}"
                             f"   ·   LOD: {f.lod_note}")

    # ------------------------------------------------------------------ 그리기
    def _redraw(self) -> None:
        if self.result is None:
            for panel in (self.panel_cal, self.panel_spec):
                panel.show_placeholder(error=self.message is not None)
        else:
            self.panel_cal.redraw(lambda ax: draw_calibration(ax, self.result, self.fit))
            self.panel_spec.redraw(lambda ax: draw_spectra(ax, self.result))
        self._fill_table()

    def _pick_peak(self, event) -> None:
        """Mean spectra 클릭 → 근처(±15 cm⁻¹)에서 가장 높은 피크를 검량선 피크로."""
        if self.result is None or event.inaxes is not self.panel_spec.ax or event.xdata is None:
            return
        if self.panel_spec.tool_active:          # 확대/이동 중이면 무시
            return
        wn = self.result.wn
        y = self.result.groups[-1].used_spectra.mean(1)      # 가장 진한 농도의 평균 스펙트럼
        near = np.abs(wn - event.xdata) <= 15
        if near.any():
            x = float(wn[near][np.argmax(y[near])])
            self.spn_center.setValue(round(x * 2) / 2)       # 0.5 cm⁻¹ 단위 → 자동 재계산
            self.flash(f"Peak set to {self.spn_center.value():g} cm⁻¹")

    def _fill_table(self) -> None:
        if self.result is None:
            self.tbl_sum.setRowCount(0)
            return
        df = cc.summary_table(self.result.groups, self.fit)
        self.tbl_sum.setRowCount(len(df))

        def num(v):
            return "–" if not np.isfinite(v) else f"{v:.1f}"

        for r, row in df.iterrows():
            fg = QColor(C["text"] if row.in_fit else C["disabled"])
            vals = [cc.format_conc(row.conc_uM), f"{row.n_used} / {row.n_total}", num(row["mean"]),
                    num(row.sd), num(row.rsd_pct), "", row.files]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setForeground(fg if c < 6 else QColor(C["secondary"]))
                if c < 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 5:
                    item.setIcon(icon("check", C["accent"], 14) if row.in_fit else icon("x", C["disabled"], 14))
                self.tbl_sum.setItem(r, c, item)
        self.tbl_sum.resizeColumnsToContents()

    # ------------------------------------------------------------------ 저장
    def _ask_stem(self, title: str, default: str) -> Path | None:
        """저장 대화상자. 고른 이름을 파일 접두어로 씀 (확장자는 떼어 냄)."""
        path, _ = QFileDialog.getSaveFileName(self, title, str(Path(self.last_dir or ".") / default), "All files (*)")
        if not path:
            return None
        p = Path(path)
        if p.suffix.lower() in (".png", ".pdf", ".svg", ".csv", ".txt"):
            p = p.with_suffix("")
        self.last_dir = str(p.parent)
        return p

    def copy_figure(self, canvas) -> None:
        QApplication.clipboard().setImage(canvas.grab().toImage())
        self.flash("Figure copied to clipboard")

    def save_figure(self, which: str) -> None:
        if self.result is None:
            return
        stem = self._ask_stem("Save figure (PDF, PNG and SVG)", which)
        if stem is None:
            return
        try:
            if which == "calibration":
                fig, ax = fs.figure()
                draw_calibration(ax, self.result, self.fit)
            else:
                fig, ax = fs.figure(square=False, width_cm=16)
                draw_spectra(ax, self.result)
            export_figure(fig, stem)
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))
            return
        self.flash(f"Saved {stem.name}.pdf / .png / .svg")

    def export(self) -> None:
        if self.result is None or self.fit is None:
            return
        stem = self._ask_stem("Export results — the name is used as the file prefix", "calibration")
        if stem is None:
            return
        r, out, pre = self.result, stem.parent, stem.name
        lines = cc.result_lines(self.fit, r.blank, self.spn_mw.value())
        lines += ["",
                  "Settings: " + ", ".join(f"{k}={v}" for k, v in asdict(r.settings).items()),
                  "Blank files: " + (", ".join(r.blank.files) if r.blank else "(none)"),
                  "Sample files: " + ", ".join(f for g in r.groups for f in g.files)]
        try:
            cc.summary_table(r.groups, self.fit).to_csv(out / f"{pre}_summary.csv", index=False, encoding="utf-8-sig")
            cc.per_spectrum_table(r.groups).to_csv(out / f"{pre}_per_spectrum.csv", index=False, encoding="utf-8-sig")
            cc.mean_sd_spectra(r.wn, r.groups).to_csv(out / f"{pre}_mean_sd_spectra.csv", index=False)
            (out / f"{pre}_fit.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            fig, ax = fs.figure()
            draw_calibration(ax, r, self.fit)
            export_figure(fig, out / f"{pre}_calibration")
            fig, ax = fs.figure(square=False, width_cm=16)
            draw_spectra(ax, r)
            export_figure(fig, out / f"{pre}_mean_spectra")
        except Exception as e:
            QMessageBox.critical(self, "Export error", str(e))
            return
        self.flash(f"Exported {pre}_… to {out}")


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    w = CalibrationWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

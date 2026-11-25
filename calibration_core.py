"""
SERS 검량선 계산 (화면 없이 쓰는 부분).

순서
    1) 파일 읽기 (TXT 스펙트럼 묶음 / 라만 맵 CSV)
    2) spike 제거 (Hampel) → baseline 빼기 (ALS / airPLS) → Savitzky–Golay smoothing
    3) 피크 높이: [중심 - 반폭, 중심 + 반폭] 창 양 끝 3점 평균을 잇는 직선 위로 올라온 최댓값
    4) 농도마다 (선택) 최댓값·최솟값 스펙트럼 1개씩 제외 → 평균 ± SD
    5) 블랭크 평균 + 3SD = 검출 기준
    6) log I = a log C + b  (또는 I = a C + b) 맞춤, LOD 계산

농도는 µM 단위로 다룸. 파일 이름의 '100nM', '2-5uM'(=2.5 µM), '1 mM' 같은 표기를 읽음.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from pybaselines import Baseline
from scipy.signal import medfilt, savgol_filter

UNIT_TO_UM = {"p": 1e-6, "n": 1e-3, "u": 1.0, "µ": 1.0, "μ": 1.0, "m": 1e3}
# 대소문자 구분: 'nM'(농도)은 읽고 '785 nm'(파장)은 무시
_CONC_RE = re.compile(r"(?<![\d.])(\d+(?:[.\-]\d+)?)\s*([pnuµμm])M(?![a-zA-Z])")


# ----------------------------------------------------------------------------- 읽기
def parse_concentration(name: str) -> float | None:
    """파일 이름에서 농도(µM)를 읽음. 못 찾으면 None.
    '2-5uM' = 2.5 (하이픈은 소수점), '025uM' = 0.25, '05uM' = 0.5 (0으로 시작하는 숫자는 0.xx)."""
    for m in _CONC_RE.finditer(name):
        num, unit = m.group(1).replace("-", "."), m.group(2)
        if re.fullmatch(r"0\d+", num):
            num = "0." + num[1:]
        try:
            return float(num) * UNIT_TO_UM[unit]
        except (ValueError, KeyError):
            continue
    return None


def load_spectra(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """(wavenumber, 스펙트럼 행렬 [점 수 × 스펙트럼 수]) 반환.

    - TXT: 첫 열 wavenumber, 나머지 열이 스펙트럼 (공백/탭 구분). 첫 열이 1,2,3… 순번이면 둘째 열이 wavenumber.
    - CSV: 'X num / Y num / X,Y,wn…' 라만 맵이면 픽셀마다 스펙트럼 하나. 아니면 TXT와 같은 표로 읽음.
    """
    path = Path(path)
    if path.stat().st_size == 0:
        raise ValueError(f"{path.name}: empty file")
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        first = fh.readline()
        fh.readline()
        header = fh.readline()
    if path.suffix.lower() == ".csv" and first.lower().lstrip().startswith("x num"):
        toks = [t.strip() for t in header.rstrip("\r\n").split(",")]
        while toks and toks[-1] == "":
            toks.pop()
        wn = np.asarray(toks[2:], dtype=float)
        data = pd.read_csv(path, skiprows=3, header=None).dropna(axis=1, how="all").to_numpy(dtype=float)
        Y = data[:, 2:2 + len(wn)].T
    else:
        sep = "," if path.suffix.lower() == ".csv" else r"\s+"
        df = pd.read_csv(path, sep=sep, header=None, engine="python").dropna(axis=1, how="all")
        try:
            a = df.to_numpy(dtype=float)
        except ValueError:
            raise ValueError(f"{path.name}: no numeric columns") from None
        if a.shape[1] >= 3 and np.allclose(a[:, 0], np.arange(1, len(a) + 1)):
            a = a[:, 1:]
        if a.shape[1] < 2:
            raise ValueError(f"{path.name}: needs a wavenumber column and at least one spectrum column")
        wn, Y = a[:, 0], a[:, 1:]
    if Y.shape[0] != len(wn) or Y.shape[1] == 0:
        raise ValueError(f"{path.name}: no spectra found")
    if not np.all(np.isfinite(Y)):
        raise ValueError(f"{path.name}: contains empty (NaN) values")
    return wn, Y


# ----------------------------------------------------------------------------- 전처리
@dataclass
class Settings:
    despike: bool = True
    spike_thr: float = 7.0
    spike_win: int = 5
    algo: str = "ALS"            # "ALS" / "airPLS"
    lam: float = 1e5
    p: float = 0.01
    max_iter: int = 50
    smooth_window: int = 7       # 0 또는 1이면 smoothing 안 함 (홀수)
    smooth_order: int = 2
    peak_center: float = 1013.0  # cm-1
    peak_halfwidth: float = 17.5 # cm-1
    trim: bool = True            # 농도마다 최대·최소 1개씩 제외
    dilution: float = 1.0        # 파일 이름 농도 × dilution = 실제 농도


def despike(Y: np.ndarray, thr: float = 7.0, win: int = 5) -> np.ndarray:
    k = max(3, int(win)) | 1
    out = np.array(Y, dtype=float, copy=True)
    if out.shape[0] < k:
        return out
    for j in range(out.shape[1]):
        y = out[:, j]
        med = medfilt(y, k)
        dev = np.abs(y - med)
        s = 1.4826 * np.median(dev)
        if s <= 0:
            nz = dev[dev > 0]
            if nz.size == 0:
                continue
            s = 1.4826 * np.median(nz)
        bad = dev > thr * s
        y[bad] = med[bad]
    return out


def preprocess(wn: np.ndarray, Y: np.ndarray, s: Settings) -> np.ndarray:
    """spike 제거 → baseline 빼기 → smoothing. 반환: baseline 뺀 스펙트럼."""
    if s.despike:
        Y = despike(Y, s.spike_thr, s.spike_win)
    fit = Baseline(x_data=wn)
    C = np.empty_like(Y, dtype=float)
    for i in range(Y.shape[1]):
        if s.algo == "ALS":
            b = fit.asls(Y[:, i], lam=s.lam, p=s.p, max_iter=s.max_iter)[0]
        elif s.algo == "airPLS":
            b = fit.airpls(Y[:, i], lam=s.lam, max_iter=s.max_iter)[0]
        else:
            raise ValueError(f"unknown baseline algorithm: {s.algo}")
        C[:, i] = Y[:, i] - b
    w = int(s.smooth_window)
    if w > 1:
        w |= 1
        if w <= s.smooth_order:
            raise ValueError("smoothing window must be larger than the smoothing order")
        C = savgol_filter(C, w, s.smooth_order, axis=0)
    return C


def peak_heights(wn: np.ndarray, C: np.ndarray, center: float, halfwidth: float) -> np.ndarray:
    m = (wn >= center - halfwidth) & (wn <= center + halfwidth)
    if m.sum() < 7:
        raise ValueError(f"peak window {center:g} ± {halfwidth:g} cm⁻¹ has too few points ({m.sum()}) — check Peak center")
    x, V = wn[m], C[m]
    a, b = V[:3].mean(0), V[-3:].mean(0)
    line = a + np.outer((x - x[0]) / (x[-1] - x[0]), b - a)
    return (V - line).max(0)


def trim_mask(v: np.ndarray, on: bool = True) -> np.ndarray:
    keep = np.ones(len(v), bool)
    if on and len(v) >= 4:
        keep[np.argmax(v)] = False
        keep[np.argmin(v)] = False
    return keep


def prep_key(s: Settings) -> tuple:
    """전처리(spike·baseline·smoothing)에 영향을 주는 설정만. 피크 위치·희석·제외 규칙은 빠짐."""
    return (s.despike, s.spike_thr, s.spike_win, s.algo, s.lam, s.p, s.max_iter,
            s.smooth_window, s.smooth_order)


class SpectraCache:
    """파일별 전처리 결과 저장. 전처리 설정과 파일 수정 시각이 같으면 다시 계산하지 않음
    → 피크 위치, 창 폭, 희석 배수, 최대·최소 제외를 바꿀 때 즉시 다시 계산 가능."""

    def __init__(self) -> None:
        self._d: dict[str, tuple[tuple, np.ndarray, np.ndarray]] = {}

    def has(self, path: str | Path, s: Settings) -> bool:
        """이 설정으로 이미 처리해 둔 파일이면 True (화면의 '계산 중' 표시 여부 판단용)."""
        path = Path(path)
        try:
            key = (prep_key(s), path.stat().st_mtime_ns)
        except OSError:
            return False
        hit = self._d.get(str(path))
        return hit is not None and hit[0] == key

    def get(self, path: str | Path, s: Settings) -> tuple[np.ndarray, np.ndarray]:
        path = Path(path)
        key = (prep_key(s), path.stat().st_mtime_ns)
        hit = self._d.get(str(path))
        if hit is not None and hit[0] == key:
            return hit[1], hit[2]
        wn, Y = load_spectra(path)
        C = preprocess(wn, Y, s)
        self._d[str(path)] = (key, wn, C)
        return wn, C


def _corrected(path: str | Path, s: Settings, cache: SpectraCache | None):
    if cache is not None:
        return cache.get(path, s)
    wn, Y = load_spectra(path)
    return wn, preprocess(wn, Y, s)


# ----------------------------------------------------------------------------- 결과
def in_range(conc: float, lo: float, hi: float) -> bool:
    """lo ≤ conc ≤ hi (농도 반올림 오차 허용)."""
    return lo * (1 - 1e-9) <= conc <= hi * (1 + 1e-9)


@dataclass
class Group:
    """한 농도의 모든 스펙트럼. used = 최대·최소 제외 뒤 남은 스펙트럼 표시."""
    conc: float                       # µM (희석 반영)
    files: list[str] = field(default_factory=list)
    heights: np.ndarray = field(default_factory=lambda: np.empty(0))
    used: np.ndarray = field(default_factory=lambda: np.empty(0, bool))
    source: list[tuple[str, int]] = field(default_factory=list)   # (파일 이름, 스펙트럼 번호)
    spectra: np.ndarray | None = None  # 보정된 스펙트럼 전부 (점 × 스펙트럼), heights와 같은 순서

    @property
    def mean(self) -> float:
        return float(self.heights[self.used].mean())

    @property
    def sd(self) -> float:
        v = self.heights[self.used]
        return float(v.std(ddof=1)) if len(v) > 1 else float("nan")

    @property
    def used_spectra(self) -> np.ndarray:
        return self.spectra[:, self.used]


@dataclass
class Blank:
    mean: float
    sd: float
    n: int
    files: list[str]

    @property
    def threshold(self) -> float:
        """검출 기준 = 블랭크 평균 + 3SD"""
        return self.mean + 3 * self.sd


@dataclass
class Fit:
    kind: str                # "loglog" / "linear"
    slope: float
    intercept: float
    r2: float
    lo: float                # 맞춤 구간 (µM)
    hi: float
    lod: float | None        # µM
    lod_note: str

    def contains(self, conc: float) -> bool:
        return in_range(conc, self.lo, self.hi)

    def equation(self) -> str:
        sign = "+" if self.intercept >= 0 else "−"
        if self.kind == "loglog":
            return f"log I = {self.slope:.3f} log C {sign} {abs(self.intercept):.3f}"
        return f"I = {self.slope:.4g} C {sign} {abs(self.intercept):.4g}"


def format_conc(c: float) -> str:
    return f"{c * 1000:.3g} nM" if c < 1 else f"{c:.4g} µM"


def process_groups(files: list[tuple[str | Path, float]], s: Settings, keep_spectra: bool = True,
                   cache: SpectraCache | None = None):
    """files: [(경로, 파일 이름 농도 µM)] → (wn, [Group…] 농도 오름차순)."""
    groups: dict[float, Group] = {}
    wn_ref = None
    for path, conc in files:
        path = Path(path)
        wn, C = _corrected(path, s, cache)
        if wn_ref is None:
            wn_ref = wn
        elif len(wn) != len(wn_ref) or not np.allclose(wn, wn_ref):
            raise ValueError(f"{path.name}: wavenumber axis differs from the first file")
        h = peak_heights(wn, C, s.peak_center, s.peak_halfwidth)
        c = round(float(conc) * s.dilution, 12)
        g = groups.setdefault(c, Group(conc=c))
        g.files.append(path.name)
        g.heights = np.concatenate([g.heights, h])
        g.source += [(path.name, i + 1) for i in range(len(h))]
        if keep_spectra:
            g.spectra = C if g.spectra is None else np.hstack([g.spectra, C])
    out = [groups[c] for c in sorted(groups)]
    for g in out:
        g.used = trim_mask(g.heights, s.trim)
    return wn_ref, out


def blank_threshold(files: list[str | Path], s: Settings, cache: SpectraCache | None = None) -> Blank:
    """블랭크 파일(들) → Blank. 샘플과 같은 처리, 같은 최대·최소 제외 규칙."""
    hs = []
    for path in files:
        wn, C = _corrected(path, s, cache)
        hs.append(peak_heights(wn, C, s.peak_center, s.peak_halfwidth))
    h = np.concatenate(hs)
    h = h[trim_mask(h, s.trim)]
    if len(h) < 2:
        raise ValueError("the blank needs at least 2 spectra")
    return Blank(float(h.mean()), float(h.std(ddof=1)), len(h), [Path(f).name for f in files])


def auto_range(conc: np.ndarray, mean: np.ndarray, thr: float | None) -> tuple[float, float]:
    """맞춤 구간 자동: 블랭크+3SD보다 큰 첫 농도 ~ 평균이 가장 큰 농도 (그 위는 포화로 봄)."""
    hi = float(conc[int(np.argmax(mean))])
    ok = (mean > thr) if thr is not None else np.ones(len(conc), bool)
    cand = conc[ok & (conc <= hi)]
    lo = float(cand.min()) if len(cand) else float(conc.min())
    return lo, hi


def fit_curve(groups: list[Group], kind: str, lo: float, hi: float, blank: Blank | None) -> Fit:
    c = np.array([g.conc for g in groups])
    m = np.array([g.mean for g in groups])
    sel = np.array([in_range(x, lo, hi) for x in c])
    if sel.sum() < 2:
        raise ValueError("the fitted range needs at least 2 concentrations")
    if kind == "loglog":
        if np.any(c[sel] <= 0) or np.any(m[sel] <= 0):
            raise ValueError("log-log fit needs concentrations and intensities above 0")
        X, Y = np.log10(c[sel]), np.log10(m[sel])
    else:
        X, Y = c[sel], m[sel]
    slope, icpt = np.polyfit(X, Y, 1)
    ss_res = ((Y - (icpt + slope * X)) ** 2).sum()
    ss_tot = ((Y - Y.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    lod, note = None, "no blank"
    if blank is not None:
        if slope <= 0:
            note = "slope ≤ 0 — LOD not available"
        elif kind == "loglog":
            if blank.threshold > 0:
                lod, note = 10 ** ((np.log10(blank.threshold) - icpt) / slope), "blank mean + 3SD substituted into the fit"
            else:
                note = "blank + 3SD ≤ 0 — LOD not available"
        else:
            lod, note = 3 * blank.sd / slope, "3 SD(blank) / slope"
    return Fit(kind, float(slope), float(icpt), float(r2), float(lo), float(hi),
               None if lod is None else float(lod), note)


def result_lines(fit: Fit, blank: Blank | None, mw: float = 0.0) -> list[str]:
    """화면·저장에 같이 쓰는 결과 문장 (일반 텍스트). 0번 = 식, 마지막 = LOD."""
    lines = [f"{fit.equation()}   (C in µM)   R² = {fit.r2:.4f}   "
             f"fit {format_conc(fit.lo)} – {format_conc(fit.hi)}"]
    if blank is not None:
        lines.append(f"Blank: {blank.mean:.1f} ± {blank.sd:.1f} (n={blank.n}), "
                     f"mean + 3SD = {blank.threshold:.1f}")
    if fit.lod is None:
        lines.append(f"LOD: {fit.lod_note}")
    else:
        mgl = f" = {fit.lod * mw / 1000:.3g} mg/L" if mw > 0 else ""
        lines.append(f"LOD = {format_conc(fit.lod)}{mgl}   ({fit.lod_note})")
    return lines


def summary_table(groups: list[Group], fit: Fit | None) -> pd.DataFrame:
    rows = []
    for g in groups:
        rows.append(dict(conc_uM=g.conc, n_used=int(g.used.sum()), n_total=len(g.heights),
                         mean=g.mean, sd=g.sd, rsd_pct=100 * g.sd / g.mean if g.mean else np.nan,
                         in_fit=fit is not None and fit.contains(g.conc), files="; ".join(g.files)))
    return pd.DataFrame(rows)


def per_spectrum_table(groups: list[Group]) -> pd.DataFrame:
    rows = []
    for g in groups:
        for (f, i), h, u in zip(g.source, g.heights, g.used):
            rows.append(dict(conc_uM=g.conc, file=f, spectrum=i, height=h, used=bool(u)))
    return pd.DataFrame(rows)


def mean_sd_spectra(wn: np.ndarray, groups: list[Group]) -> pd.DataFrame:
    """농도별 (최대·최소 제외 뒤) 평균·SD 스펙트럼."""
    cols = {"wavenumber": wn}
    for g in groups:
        S = g.used_spectra
        cols[f"{g.conc:g}uM_mean"] = S.mean(1)
        cols[f"{g.conc:g}uM_sd"] = S.std(1, ddof=1) if S.shape[1] > 1 else np.full(len(wn), np.nan)
    return pd.DataFrame(cols)

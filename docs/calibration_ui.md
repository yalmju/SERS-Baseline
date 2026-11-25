# SERS Calibration — UI 명세 (Figma 작업용)

> **v2 반영됨 (2026-11-25)** — 아래 §7 약점 7가지를 앱에 반영했어요 (Figma 플러그인 v2 디자인 기준).
> Export는 탭 오른쪽, 4단계는 "Fit"만 · 파일 표 Spectra 열 / 손으로 고친 농도 초록 점 / 잘못된 값·못 읽은 파일 빨간 표시 ·
> 빈 표 대신 드롭 영역 + 끌어올 때 강조 · 계산 중 회색 카드 + 진행 막대 · 자체 툴바 (Reset view · Zoom · Pan │ Save figure · Copy + 좌표) ·
> UI 글자 영어로 통일 · LOD 카드에 mg/L와 blank + 3SD. 새 색 토큰 `color.accent.subtle` `#EAF6F0`, `color.danger-subtle` `#FDF1EA`.
> 아래 측정값·캡처는 v1 기준이라 위치가 조금 달라요.

`calibration_app.py` 화면을 Figma에서 다시 디자인할 때 쓰는 기준 문서예요.
값은 모두 현재 코드에서 그대로 가져왔어요. 그래프 안쪽 스타일(Arial 18 pt 등)은 `figstyle.py`가 정하므로 여기서는 다루지 않아요.

- 토큰 파일: [`calibration_ui_tokens.json`](calibration_ui_tokens.json) (W3C Design Tokens 형식 → Tokens Studio 플러그인으로 Figma Variables에 가져오기)
- 크기 단위: Qt는 글자를 pt로 씀. Windows 100% 배율 기준 **1 pt = 1.333 px** 로 바꿔 적었어요.

## 1. 화면 구조

기본 창 1400 × 880 px (최소 크기 제한 없음). 좌우 2단, 가운데 경계는 끌어서 폭 조절 가능 (QSplitter).

```
┌───────────── 440 ─────────────┬──────────────────────── 960 ───────────────────────────┐
│ Side panel (scroll, #F4F5F7)  │ Results (#F4F5F7)                                      │
│  ┌ 1 Sample spectra ───────┐  │  ┌Calibration───┐┌R²──┐┌LOD─────┐┌Fitted range┐  h 85  │
│  │ hint                    │  │  └──────────────┘└────┘└────────┘└────────────┘        │
│  │ [file table  h≥200]     │  │  detail line (blank 값 / LOD 방법 / 오류)       h 16   │
│  │ [Add files][Remove][Clear]│  │  ┌ Calibration curve | Mean spectra | Summary table ┐ │
│  └─────────────────────────┘  │  │ matplotlib toolbar (icon 18)                      │ │
│  ┌ 2 Blank ────────────────┐  │  │                                                   │ │
│  ┌ 3 Processing ───────────┐  │  │            plot / table   (h ≈ 709)               │ │
│  │  ▸ Baseline and smoothing│  │  │                                                   │ │
│  ┌ 4 Fit and export ───────┐  │  └───────────────────────────────────────────────────┘ │
│  │ [Export results…]       │  │                                                        │
└───────────────────────────────┴────────────────────────────────────────────────────────┘
 status bar (h ≈ 22): "10 files · 8 concentrations"
```

측정값 (창 1400 × 880):

| 영역 | x | y | w | h |
| --- | --- | --- | --- | --- |
| Side panel (스크롤 영역) | 0 | 0 | 440 | 858 |
| Metric card · Calibration | 454 | 14 | 338 | 85 |
| Metric card · R² | 802 | 14 | 113 | 85 |
| Metric card · LOD | 925 | 14 | 226 | 85 |
| Metric card · Fitted range | 1161 | 14 | 225 | 85 |
| Detail line | 454 | 109 | 932 | 16 |
| Tabs (그래프/표) | 454 | 135 | 932 | 709 |

- Metric card 폭 비율 3 : 1 : 2 : 2, 카드 사이 10 px
- Side panel 안쪽 여백 좌 14 · 위 14 · 우 10 · 아래 14, 카드 사이 12 px
- Results 안쪽 여백 좌 10 · 위 14 · 우 14 · 아래 14, 요소 사이 10 px

## 2. 디자인 토큰

### 색

| 토큰 | 값 | 쓰는 곳 |
| --- | --- | --- |
| `color.bg.app` | `#F4F5F7` | 창 배경, side panel |
| `color.bg.surface` | `#FFFFFF` | 카드, 탭 영역, 입력칸, 버튼 |
| `color.bg.table-header` | `#F3F4F6` | 표 머리글 |
| `color.bg.table-alt` | `#FAFBFC` | 표 짝수 줄 |
| `color.bg.button-hover` | `#F0F2F5` | 보조 버튼 hover |
| `color.border.card` | `#E3E6EA` | 카드·표 테두리, 표 머리글 아래선 |
| `color.border.control` | `#D0D4DA` | 버튼·입력칸 테두리 |
| `color.border.grid` | `#EEF0F3` | 표 격자선 |
| `color.text.primary` | `#1F2937` | 기본 글자 |
| `color.text.strong` | `#111827` | 선택된 탭 |
| `color.text.secondary` | `#6B7280` | 안내문, 카드 제목, 탭 |
| `color.text.toggle` | `#4B5563` | 접기 버튼 글자 |
| `color.text.disabled` | `#A0A6AE` | 꺼진 버튼 글자 |
| `color.accent` | `#2BA36B` | 주 버튼, 단계 번호, 그래프 데이터 |
| `color.accent.hover` | `#24905E` | 주 버튼 hover |
| `color.accent.disabled` | `#A9D9C1` | 주 버튼 꺼짐 |
| `color.danger` | `#C2410C` | 입력 오류 안내 |
| `color.plot.gray` | `#7A7A7A` | 그래프 보조선 (blank + 3SD) |
| `color.plot.pink` | `#F0507A` | 피크 창 표시 (15% 투명도) |

### 글자

글꼴: `Segoe UI` (영문), 한글은 `Malgun Gothic`으로 대체.

| 토큰 | pt | px | 굵기 | 쓰는 곳 |
| --- | --- | --- | --- | --- |
| `type.body` | 10 | 13.3 | 400 | 기본 (라벨, 버튼, 표, 입력) |
| `type.section-title` | 11 | 14.7 | 600 | 카드 제목 ("Sample spectra") |
| `type.metric-value` | 15 | 20 | 600 | 결과 카드 값 ("323 nM") |
| `type.caption` | 9 | 12 | 400 | 안내문, 카드 제목, 카드 보조 줄 |
| `type.badge` | 10 | 13.3 | 700 | 단계 번호 원 안 숫자 |
| `type.button-primary` | 10 | 13.3 | 600 | 주 버튼 |

### 모서리·간격

| 토큰 | 값 |
| --- | --- |
| `radius.card` | 10 px |
| `radius.tab-pane` | 8 px |
| `radius.button` / `radius.table` / `radius.tab` | 6 px |
| `radius.input` | 5 px |
| `radius.badge` | 10 px (지름 20 원) |
| `space.card-padding` | 좌우 14 · 위 12 · 아래 14 |
| `space.metric-padding` | 좌우 14 · 위아래 10, 줄 사이 2 |
| `space.section-body` | 8 (카드 안 요소 사이) |
| `space.form-column` | 12 (라벨-입력 사이) |
| `space.stack` | 12 (side 카드 사이), 10 (결과 영역 요소 사이) |
| 버튼 padding | 보조 6 × 12, 주 버튼 9 (전체) |
| 탭 padding | 7 × 16 |
| 입력칸 padding | 3 × 6 (combo, text), spin 2 × 4 |

그림자 없음, 테두리 1 px로만 구분.

## 3. 컴포넌트

| 컴포넌트 | 구성 | 상태 |
| --- | --- | --- |
| **Section card** | 흰 카드 + 단계 번호 원(20 px, accent) + 제목 + 본문 | – |
| **Metric card** | 제목(caption, secondary) / 값(metric-value) / 보조 줄(caption) | 빈 상태 값 "–" |
| **Primary button** | accent 배경, 흰 글자 | normal · hover · disabled (Export는 결과가 있을 때만 켜짐) |
| **Secondary button** | 흰 배경, control 테두리 | normal · hover · disabled |
| **Number input** | Qt 기본 spin box (위/아래 화살표) | normal · disabled (Automatic range 켜면 범위 칸 꺼짐) |
| **Dropdown** | Model (log-log / Linear), Baseline (ALS / airPLS) | – |
| **Checkbox** | Exclude highest and lowest…, Remove spikes, Automatic range | on · off |
| **Collapsible** | 화살표 + 굵은 회색 글자 "Baseline and smoothing" | 접힘(기본) · 펼침 |
| **File table (drop zone)** | 2열: File(늘어남) / Conc (µM)(편집 가능), 줄무늬, 행 번호 없음 | 빈 표 · 파일 있음 · 끌어다 놓는 중(현재 별도 표시 없음) |
| **Tabs** | Calibration curve / Mean spectra / Summary table | 선택 탭만 흰 배경 + 굵게 |
| **Plot area** | matplotlib 툴바(홈·뒤로·앞으로·이동·확대·설정·축·저장) + 그래프 | 빈 상태 안내 문구 / 결과 / 오류 안내 문구 |
| **Summary table** | Conc · n used / total · Mean · SD · RSD (%) · In fit(✓) · Files | 읽기 전용 |
| **Detail line** | 블랭크 값 · LOD 계산 방법, 오류면 주황 글자 | 정상 · 오류 |
| **Status bar** | "10 files · 8 concentrations", "Calculating…", "Peak set to 1597.5 cm⁻¹" | 4초 뒤 사라짐 |

## 4. 화면 상태

캡처: `ui_screens/` (공개 저장소에는 넣지 않음 — 실험 파일 이름이 보임)

| 파일 | 상태 |
| --- | --- |
| `01_empty.png` | 처음 연 화면. 카드 "–", 그래프 자리에 "Drop spectra files on the left to start" |
| `02_result_calibration.png` | 파일 10개 + 블랭크. 카드에 식·R²·LOD·범위, 검량선 그래프 |
| `03_result_mean_spectra.png` | 농도별 평균 스펙트럼, 분홍 = 피크 창 |
| `04_result_summary_table.png` | 농도별 표 |
| `05_linear_model.png` | Model = Linear일 때 |
| `06_advanced_open_scrolled.png` | Baseline and smoothing 펼침 → side panel이 길어져 스크롤 |
| `07_error_state.png` | 농도 칸에 잘못된 값 → 카드 "–", detail line 주황 글자, 그래프 자리 "Check the settings on the left" |

## 5. 상호작용

| 동작 | 결과 |
| --- | --- |
| 파일을 표에 끌어다 놓기 / Add files… | 표에 추가, 농도는 파일 이름에서 자동 입력 (`100nM`, `2-5uM`, `1 mM`) |
| 아무 입력이나 바꿈 (파일, 농도 칸, 블랭크, Processing 값, 체크) | **0.25초 동안 추가 입력이 없으면 자동 재계산**. Run 버튼 없음 |
| 피크 위치·창·희석·제외 규칙 변경 | 저장해 둔 보정 스펙트럼으로 약 0.1–0.2초 안에 반영 |
| Baseline·smoothing 변경 | 스펙트럼 다시 처리, 약 0.6초 (그동안 대기 커서) |
| Fit 영역 변경 (Model, 범위, MW) | 즉시 반영 |
| Automatic range 켬 | 범위 칸이 꺼지고 자동 값으로 채워짐 |
| Mean spectra 그래프 클릭 | 클릭 위치 ±15 cm⁻¹ 안 가장 높은 피크로 Peak center 변경 → 재계산 (확대/이동 도구 사용 중이면 무시) |
| 잘못된 입력 | 팝업 없이 detail line에 주황 글자로 이유 (저장 오류만 팝업) |
| Export results… | 폴더 선택 → CSV 3개, fit.txt, 그림 PDF/PNG/SVG 2종 |

## 6. 문구 목록

- 제목: `Sample spectra`, `Blank (no analyte)`, `Processing`, `Fit and export`
- 버튼: `Add files…`, `Remove`, `Clear`, `Choose blank…`, `Clear`, `Export results…`
- 라벨: `Dilution factor`, `Peak center (cm⁻¹)`, `Window ± (cm⁻¹)`, `Smoothing window`, `Smoothing order`, `Baseline`, `λ`, `p`, `Max iterations`, `Model`, `Range (µM)`, `MW (g/mol)`, `File prefix`
- 체크: `Exclude highest and lowest spectrum per concentration`, `Remove spikes`, `Automatic range`
- 카드: `Calibration`, `R²`, `LOD`, `Fitted range`
- 탭: `Calibration curve`, `Mean spectra`, `Summary table`
- 안내(한국어): 파일 넣는 법 / 블랭크는 원본 파일 / 값을 바꾸면 바로 계산·피크 클릭

## 7. 다시 디자인할 때 볼 점 (현재 약점)

1. **4단계(Fit and export)가 화면 아래로 밀림.** 880 px 높이에서 고급 설정을 펼치면 Export 버튼이 스크롤해야 보임. Export를 결과 쪽 위(카드 줄 오른쪽 등)로 옮기는 안.
2. **파일 표가 정보 부족.** 파일별 스펙트럼 개수, 읽기 오류, 농도 자동/수동 구분이 안 보임.
3. **끌어다 놓을 때 표시 없음.** drop zone 강조(점선 테두리, 배경색) 필요.
4. **계산 중 표시가 커서뿐.** 0.6초 재처리 동안 카드나 그래프에 진행 표시 없음.
5. **matplotlib 기본 툴바.** 아이콘 모양이 나머지 UI와 다름. 필요한 것(확대 초기화, 그림 저장)만 남기는 안.
6. **한/영 섞임.** 라벨은 영어, 안내문은 한국어. 한쪽으로 통일할지 결정 필요.
7. **LOD 카드에 근거가 안 보임.** blank + 3SD 값과 방법이 detail line에 작게만 있음.

## 8. 구현 제약 (PyQt6 + Qt Style Sheet)

Figma에서 디자인해도 그대로 옮기기 어려운 것:
- **그림자(box-shadow), blur, 그라데이션 테두리**: QSS 미지원 → 테두리·배경색으로만 구분
- **애니메이션**: 상태 전환 애니메이션은 별도 코드 필요 (기본은 없음)
- **spin box 화살표, 체크박스, 스크롤바**: 운영체제/Fusion 스타일 기본 모양. 바꾸려면 아이콘 이미지 필요
- **글꼴**: 사용자 PC에 있는 글꼴만 (기본 Segoe UI / 맑은 고딕). Pretendard 등은 exe에 넣어야 함
- **그래프 안쪽**: figstyle 규칙 고정 (Arial 18 pt, 초록 마커). 그래프 바깥(툴바, 여백, 배경)만 디자인 대상
- **아이콘**: 지금은 아이콘 없음. 넣으려면 SVG 파일로 받으면 됨

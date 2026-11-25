# SERS Baseline

라만/SERS 스펙트럼에서 튀는 값(spike)을 지우고 배경(baseline)을 빼 주는 GUI 프로그램이에요.
보정한 스펙트럼의 평균과 표준편차도 같이 저장해요.

| 파일 | 하는 일 |
| --- | --- |
| `app.py` | 프로그램 본체 (PyQt6 창) |
| `SERS_Baseline.spec` | exe 하나로 묶는 PyInstaller 설정 |
| `README.txt`, `README.pdf` | exe와 같이 나눠 주는 설명서 (Baseline 프로그램 내용) |
| `calibration_app.py` | 검량선·LOD 계산 프로그램 (따로 실행, 아래 [검량선 프로그램](#검량선-프로그램-sers-calibration)) |
| `calibration_core.py` | 검량선 계산 부분 (화면 없이 import해서 쓸 수 있음) |
| `SERS_Calibration.spec` | 검량선 프로그램을 exe로 묶는 설정 |
| `figstyle.py` | 검량선 프로그램 그림 스타일 (Arial 18 pt) |

## 설치

exe만 쓸 때는 `SERS_Baseline.exe`를 더블클릭하면 돼요. 설치는 필요 없어요.
처음 켤 때 창이 뜨기까지 몇 초 걸리는데, 실행할 때마다 내부 파일을 임시 폴더에 푸는 과정이라 정상이에요.

코드로 실행하려면:

```bash
git clone https://github.com/yalmju/SERS-Baseline.git
pip install -r SERS-Baseline/requirements.txt
python SERS-Baseline/app.py
```

exe를 새로 만들려면 `pip install pyinstaller` 후 `pyinstaller SERS_Baseline.spec`을 실행해요. `dist/SERS_Baseline.exe`가 생겨요.

## 사용 순서

1. **Open TXT / CSV…** 로 데이터 파일을 열어요.
2. 왼쪽 **Baseline parameters**에서 알고리즘과 값을 정해요.
3. **Apply baseline** 을 누르면 아래 그래프에 보정 결과가 나와요.
4. 마음에 들면 **Save corrected CSV…** 로 저장해요.

위 그래프는 원본과 baseline, 아래 그래프는 보정된 스펙트럼이에요.

## 입력 파일

**TXT (스펙트럼 여러 개)**
- 공백이나 탭으로 구분된 숫자 표
- 첫 열 = wavenumber, 나머지 열 = 스펙트럼 하나씩
- 첫 열이 1, 2, 3 … 순번이면 행 번호로 보고 두 번째 열을 wavenumber로 써요

**CSV (라만 2D 매핑)**

```
X num,<nx>
Y num,<ny>
X,Y,<wn1>,<wn2>,...
<x>,<y>,<intensity1>,<intensity2>,...
```

`X num`으로 시작하지 않는 CSV는 TXT와 같은 형식으로 읽어요.

## 보정 설정

| 항목 | 기본값 | 뜻 |
| --- | --- | --- |
| Remove spikes | 켜짐 | baseline 전에 튀는 값(cosmic ray, 장비 글리치)을 먼저 지움 |
| spike thr | 7.0 | 낮을수록 더 많이 지움. 너무 낮으면 날카로운 실제 피크도 깎여요 |
| spike win | 5 | 비교할 주변 점 개수 (홀수) |
| Algorithm | ALS | ALS 또는 airPLS |
| λ (smoothness) | 1e5 | 클수록 baseline이 매끄러워요 |
| p (asymmetry) | 0.01 | ALS 전용. 작을수록 피크를 덜 깎아요 |
| max iter | 50 | 최대 반복 횟수 |

**spike 제거 방식**
- 각 점을 주변 중앙값과 비교해서, 크게 벗어난 1~2점짜리 뾰족한 값만 주변 중앙값으로 바꿔요.
- 라만 피크는 폭이 넓어서 그대로 남아요.
- 값을 바꾸면 위 그래프가 바로 바뀌고, 제목이 "Raw (despiked)"가 돼요. 아래 그래프와 저장 결과는 Apply baseline을 다시 눌러야 바뀌어요.

**보기 옵션**
- `Show baseline overlay`: 원본 그래프에 baseline을 점선으로 표시
- `Show mean ± sd on corrected`: 보정 그래프에 평균선과 ±1 표준편차 음영 표시
- `Spectrum`: 스펙트럼 하나만 보거나 `All overlay`로 전부 겹쳐 보기. 200개가 넘는 매핑은 목록 없이 `All overlay`와 평균으로 봐요.

## 저장 파일

- **TXT 입력** → `<이름>_corrected.csv`
  - 열: `wavenumber`, 스펙트럼들, `mean`, `sd` (표본 표준편차, ddof=1)
- **CSV 매핑 입력** → 원본과 같은 `X num / Y num / X,Y,wn` 형식
  - 그대로 2D 맵 프로그램에 다시 넣을 수 있어요

## 검량선 프로그램 (SERS Calibration)

농도별 스펙트럼 파일과 블랭크 파일을 넣으면 검량선 식, R², LOD를 계산해요. Baseline 프로그램과 따로 실행해요.

```bash
python SERS-Baseline/calibration_app.py
```

exe는 `pyinstaller SERS_Calibration.spec` → `dist/SERS_Calibration.exe`

**사용 순서** (Run 버튼 없음: 무엇이든 바꾸면 바로 다시 계산해요)
1. **Sample spectra**: 농도별 파일을 빈 칸에 끌어다 놓거나 **Add files…**. 같은 농도 파일이 여러 개면 합쳐서 계산해요.
   농도는 파일 이름에서 읽어요 (`100nM`, `2-5uM` = 2.5 µM, `025uM` = 0.25 µM, `05uM` = 0.5 µM, `1 mM`, `250pM`). 틀리면 **Conc (µM)** 칸을 눌러 고쳐요.
2. **Blank**: 분석물이 없는 블랭크의 원본 파일(baseline 빼지 않은 것). 없으면 LOD는 계산하지 않아요.
3. **Processing**: 희석 배수와 피크 위치. **Mean spectra** 탭에서 피크를 클릭하면 그 피크로 바로 바뀌어요.
4. **Fit**: 식 종류와 구간. **Calibration curve** 그래프의 점을 클릭해서 구간을 바로 바꿀 수도 있어요.
5. 탭 오른쪽 **Export results…** 로 저장해요. 저장 대화상자에 적은 이름이 파일 앞머리(prefix)가 돼요.

**화면**
- 위쪽 카드: 식 · R² · LOD (mg/L, blank + 3SD) · 맞춤 구간. 그 아래 한 줄에 블랭크 값과 LOD 계산 방법
- 탭: **Calibration curve** / **Mean spectra** (분홍 = 피크 창) / **Summary table** (맞춤 밖 농도는 회색)
- 그래프 툴바: Reset view · Zoom · Pan │ Save figure (figstyle PDF/PNG/SVG) · Copy (클립보드), 오른쪽에 커서 좌표
- 파일 표: **Spectra** 열 = 파일에 든 스펙트럼 수. 손으로 고친 농도는 초록 점, 잘못된 농도(예: `2,0`)는 빨간 칸,
  읽을 수 없는 파일은 빨간 줄과 이유가 나오고 계산에서 빠져요
- 계산 중에는 카드 값이 회색이 되고 그래프 위에 진행 막대가 나와요 (baseline·smoothing을 바꿔 스펙트럼을 다시 처리할 때)
- 오류가 있으면 카드 아래 주황 글자로 이유, 그래프 자리에 "Check the settings on the left"
- 아래 상태 줄: 왼쪽 = 파일·농도 수, 오른쪽 = 잠깐 뜨는 알림 (Peak set to …, Added 10 files 등)

**Processing 설정**

| 항목 | 기본값 | 뜻 |
| --- | --- | --- |
| Dilution factor | 1 | 파일 이름 농도 × 이 값 = 실제 농도 (1:1 희석이면 0.5) |
| Peak center | 1013 cm⁻¹ | 검량선에 쓸 피크 위치 |
| Window ± | 17.5 cm⁻¹ | 피크 창 반폭. 창 양 끝 3점 평균을 잇는 직선 위로 올라온 최댓값이 피크 높이 |
| Exclude highest and lowest… | 켜짐 | 농도마다 피크 높이가 가장 큰 것과 작은 것 1개씩 빼고 평균 ± SD (블랭크도 같게). 4개 미만이면 빼지 않음 |
| Remove spikes | 켜짐 | baseline 전에 튀는 값 제거 (Baseline 프로그램과 같음) |
| Baseline and smoothing (펼쳐서 설정) | SG 7점/2차, ALS λ 1e5, p 0.01, 50회 | baseline을 뺀 뒤 Savitzky–Golay smoothing (창 0이면 끔) |

피크 위치, 창, 희석 배수, 제외 규칙을 바꾸면 저장해 둔 보정 스펙트럼으로 바로(약 0.1–0.2초) 다시 계산하고,
baseline·smoothing을 바꾸면 스펙트럼을 다시 처리해요 (TBZ 데이터 기준 약 0.6초).

**Fit 설정**
- **Model**: `log-log` (log I = a log C + b) 또는 `Linear (y = ax + b)`
- **Automatic range**: 블랭크 평균 + 3SD보다 큰 첫 농도부터, 평균 세기가 가장 큰 농도까지 (그 위는 포화로 봄). 끄면 구간을 직접 정해요.
- **점 클릭으로 구간 정하기**: 검량선 그래프에서 점을 클릭하면 Automatic range가 꺼지고 구간이 바로 바뀌어요.
  구간 밖 점 → 그 점까지 넓힘, 구간 끝 점 → 뺌, 구간 안 점 → 가까운 쪽 끝이 그 점이 됨. 최소 2개 농도는 남겨요.
  점 위에 마우스를 올리면 오른쪽 위 좌표 칸에 클릭하면 어떻게 되는지 나와요. Zoom·Pan 중에는 클릭해도 안 바뀌어요.
- **MW**: 분자량을 넣으면 LOD를 mg/L로도 보여 줘요.

**LOD 계산**
- log-log: 블랭크 평균 + 3SD를 식에 넣어 농도로 바꾼 값
- Linear: 3 × 블랭크 SD / 기울기

**저장 파일** (`<prefix>_…`)

| 파일 | 내용 |
| --- | --- |
| `_summary.csv` | 농도별 n, 평균, SD, RSD, 맞춤 포함 여부 |
| `_per_spectrum.csv` | 스펙트럼마다 피크 높이와 `used` (최대·최소 제외 여부) |
| `_mean_sd_spectra.csv` | 농도별 보정 후 평균·SD 스펙트럼 |
| `_fit.txt` | 식, R², LOD, 블랭크 값, 계산에 쓴 설정, 사용한 파일 목록 |
| `_calibration.pdf/.png/.svg` | 검량선 그림 |
| `_mean_spectra.pdf/.png/.svg` | 농도별 평균 스펙트럼 그림 |

그림은 `figstyle.py` 규칙(Arial 18 pt, 범례 14 pt, 바깥 눈금, L자 축, 높이 10 cm, 로그축 0.1·1·10 표기)으로 저장해요.
화면의 그래프도 같은 규칙이에요. 농도는 모두 µM로 다루고, 파일마다 wavenumber 축이 같아야 해요.
화면 디자인은 [`docs/calibration_ui.md`](docs/calibration_ui.md) (토큰: [`docs/calibration_ui_tokens.json`](docs/calibration_ui_tokens.json)).

| 파일 | 하는 일 |
| --- | --- |
| `calibration_core.py` | 계산 (화면 없이 import해서 쓸 수 있음) |
| `calibration_app.py` | 화면 |
| `figstyle.py` | 그림 스타일 ([yalmju/data_rules](https://github.com/yalmju/data_rules)의 사본) |

baseline 계산은 [pybaselines](https://pybaselines.readthedocs.io/), 화면은 PyQt6 + matplotlib으로 만들었어요.

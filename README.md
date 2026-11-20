# SERS Baseline

라만/SERS 스펙트럼에서 튀는 값(spike)을 지우고 배경(baseline)을 빼 주는 GUI 프로그램이에요.
보정한 스펙트럼의 평균과 표준편차도 같이 저장해요.

| 파일 | 하는 일 |
| --- | --- |
| `app.py` | 프로그램 본체 (PyQt6 창) |
| `SERS_Baseline.spec` | exe 하나로 묶는 PyInstaller 설정 |
| `README.txt`, `README.pdf` | exe와 같이 나눠 주는 설명서 (이 문서와 같은 내용) |

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

baseline 계산은 [pybaselines](https://pybaselines.readthedocs.io/), 화면은 PyQt6 + matplotlib으로 만들었어요.

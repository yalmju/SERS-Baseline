# SERS Baseline Correction

라만/SERS 스펙트럼의 **튀는 값(spike) 제거 → baseline(배경) 보정**을 하고, 보정된 스펙트럼들의 **평균(mean)·표준편차(sd)**를 계산해 주는 GUI 프로그램입니다.

---

## 1. 실행 방법

`SERS_Baseline.exe` 파일 하나만 있으면 됩니다. 별도 설치 없이 더블클릭하면 실행됩니다.

> **처음 실행할 때 창이 뜨기까지 몇 초 걸릴 수 있습니다.** (실행할 때마다 내부 파일을 임시폴더에 풀기 때문이며 정상입니다.)

---

## 2. 사용 순서

1. **`Open TXT / CSV…`** 버튼으로 데이터 파일을 엽니다.
2. 왼쪽 **Baseline parameters**에서 알고리즘과 파라미터를 정합니다.
3. **`Apply baseline`** 버튼을 누르면 baseline을 잡고 보정 결과가 아래 그래프에 표시됩니다.
4. 결과가 마음에 들면 **`Save corrected CSV…`** 버튼으로 저장합니다.

화면 위쪽 그래프는 **원본(Raw) + baseline**, 아래쪽 그래프는 **보정된(Corrected)** 스펙트럼입니다.

---

## 3. 입력 파일 형식

### TXT (스펙트럼 묶음)
- 공백으로 구분된 숫자 표.
- 0번 열 = wavenumber, 그 뒤 열들 = 각 스펙트럼.
- 0번 열이 `1, 2, 3 …`처럼 단순 순번이면 자동으로 행 번호로 보고 **2번째 열을 wavenumber**로 사용합니다.

### CSV (라만 2D 매핑)
다음과 같은 instrument 매핑 형식을 지원합니다.
```
X num,<nx>
Y num,<ny>
X,Y,<wn1>,<wn2>,...
<x>,<y>,<intensity1>,<intensity2>,...
...
```
- `X num` 으로 시작하지 않는 일반 CSV는 TXT와 같은 형식으로 읽습니다.

---

## 4. Baseline 파라미터

| 항목 | 설명 |
|------|------|
| **Remove spikes (despike)** | 켜면 baseline 보정 전에 튀는 값(cosmic ray/장비 글리치)을 먼저 제거 (기본 켜짐) |
| **spike thr** | 스파이크 판정 민감도. 낮을수록 더 많이 제거(날카로운 실제 피크 손상 위험↑) (기본 7.0) |
| **spike win** | 스파이크 탐지에 쓰는 로컬 median 창 크기, 포인트 단위(홀수) (기본 5) |
| **Algorithm** | `ALS` (asymmetric least squares) 또는 `airPLS` |
| **λ (smoothness)** | 클수록 baseline이 더 매끄러워짐 (기본 1e5) |
| **p (asymmetry)** | ALS 전용. 작을수록 피크를 덜 깎음 (기본 0.01) |
| **max iter** | 최대 반복 횟수 (기본 50) |

> `airPLS`를 선택하면 `p` 값은 사용되지 않습니다.
>
> **Despike 동작 방식**: 각 포인트를 주변 median과 비교해, robust 임계값(scaled MAD)보다 크게 벗어난 1~2 포인트짜리 뾰족한 값만 골라 로컬 median으로 대체합니다. 실제 라만 피크는 폭이 넓어 보존됩니다. 제거가 적용되면 위쪽 그래프 제목이 **"Raw (despiked)"**로 바뀌고, 저장되는 결과(및 mean/sd)에도 반영됩니다.
>
> **실시간 미리보기**: despike 체크박스를 켜고 끄거나 `spike thr`/`spike win` 값을 바꾸면 위쪽 Raw 그래프가 **즉시** 갱신되어 효과를 바로 볼 수 있습니다. (아래 Corrected 그래프와 저장 결과는 `Apply baseline`을 눌러야 반영됩니다.)

### View 옵션
- **Show baseline overlay** — 원본 그래프에 추정된 baseline을 점선으로 표시
- **Show mean ± sd on corrected** — 보정 그래프에 평균선과 ±1 표준편차 음영 표시
- **Spectrum** — 특정 스펙트럼 하나만 보거나 `All overlay`로 전체 겹쳐 보기
  (스펙트럼이 200개를 넘는 매핑은 목록이 생략되며 `All overlay`/평균으로 확인)

---

## 5. 출력 파일

저장 시 입력 형식에 따라 결과가 달라집니다.

- **TXT 입력** → `<이름>_corrected.csv`
  - 컬럼: `wavenumber`, 각 스펙트럼 열, **`mean`**, **`sd`**
  - 표준편차는 표본 표준편차(ddof=1)로 계산됩니다.
- **CSV 매핑 입력** → 원본과 동일한 `X num / Y num / X,Y,wn` 픽셀 행 형식으로 저장
  (2D 맵으로 계속 활용 가능)

---

## 6. 참고

- baseline 계산 라이브러리: [pybaselines](https://pybaselines.readthedocs.io/)
- GUI: PyQt6 + matplotlib

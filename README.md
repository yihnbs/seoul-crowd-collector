# 서울 실시간 도시데이터 수집기

"집에 언제 갈까?" 프로젝트용. 서울 실시간 도시데이터를 30분마다 받아서 `data/` 폴더에 쌓는다.

## 처음 설정 (한 번만)

1. GitHub에서 새 저장소 만들기 (Public 추천: 무료 실행 시간 제한이 없음)
2. 이 폴더 안의 파일을 전부 올리기 (`.github` 폴더 포함)
3. 저장소 **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `SEOUL_API_KEY`
   - Secret: 서울 열린데이터광장 인증키
4. **Actions** 탭 → `collect-citydata` → **Run workflow** 로 한 번 수동 실행
5. 1~2분 뒤 `data/live/` 에 오늘 날짜 CSV가 생기면 성공

이후로는 30분마다 자동으로 돈다.

## 쌓이는 파일

| 폴더 | 내용 | 주기 |
|---|---|---|
| `data/live/날짜.csv` | 실시간 혼잡 단계, 추정 인구, 지하철 승하차(5·10·30분, 누적) | 장소마다 30분에 1행 |
| `data/fcst/날짜.csv` | 서울시 인구 예측 (앞으로 12시간, 1시간 단위) | 장소마다 30분에 최대 12행 |
| `data/events/날짜.csv` | 장소 주변 행사명·기간·장소 | 장소마다 하루 1번 |

시각 기준: `collected_at` 은 수집한 시각(KST), `ppltn_time` 은 서울시 데이터 자체의 기준 시각. 분석할 때는 `ppltn_time` 을 쓴다.

## 장소 바꾸기

`collector/places.csv` 에 줄을 추가하거나 지우면 된다. 장소코드(POI…)는 "서울시 주요 121장소 목록.xlsx" 참고.

## 호출 한도 주의

현재 20곳 × 하루 48번 = 하루 960번 호출. 인증키의 하루 한도를 확인하고, 여유가 있으면 장소를 늘리거나 주기를 줄인다 (`.github/workflows/collect.yml` 의 `cron`).

## 내 컴퓨터에서 테스트

```bash
export SEOUL_API_KEY=인증키
python collector/collect.py
```

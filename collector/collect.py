"""
서울 실시간 도시데이터 수집기

장소 목록(places.csv)을 돌면서 실시간 도시데이터를 한 번씩 호출하고,
필요한 값만 골라 날짜별 CSV에 이어 붙인다.

  data/live/YYYY-MM-DD.csv    실시간 인구 + 지하철 승하차 (호출마다 1행)
  data/fcst/YYYY-MM-DD.csv    인구 예측 12시간 (호출마다 최대 12행)
  data/events/YYYY-MM-DD.csv  행사 목록 (하루에 장소당 한 번만)

인증키는 환경변수 SEOUL_API_KEY 로 받는다. 코드에 직접 적지 않는다.
"""

import csv
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
BASE = "http://openapi.seoul.go.kr:8088/{key}/xml/citydata/1/5/{area}"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

LIVE_COLS = [
    "collected_at", "area_cd", "area_nm", "ppltn_time",
    "congest_lvl", "ppltn_min", "ppltn_max",
    "sub_stn_cnt",
    "sub_5_on_min", "sub_5_on_max", "sub_5_off_min", "sub_5_off_max",
    "sub_10_on_min", "sub_10_on_max", "sub_10_off_min", "sub_10_off_max",
    "sub_30_on_min", "sub_30_on_max", "sub_30_off_min", "sub_30_off_max",
    "sub_acml_on_min", "sub_acml_on_max", "sub_acml_off_min", "sub_acml_off_max",
]
FCST_COLS = ["collected_at", "area_cd", "area_nm", "fcst_time",
             "fcst_congest_lvl", "fcst_ppltn_min", "fcst_ppltn_max"]
EVENT_COLS = ["collected_at", "area_cd", "area_nm",
              "event_nm", "event_period", "event_place", "event_x", "event_y", "event_url"]

# 응답 태그 → 우리 열 이름
SUB_MAP = {
    "SUB_STN_CNT": "sub_stn_cnt",
    "SUB_5WTHN_GTON_PPLTN_MIN": "sub_5_on_min", "SUB_5WTHN_GTON_PPLTN_MAX": "sub_5_on_max",
    "SUB_5WTHN_GTOFF_PPLTN_MIN": "sub_5_off_min", "SUB_5WTHN_GTOFF_PPLTN_MAX": "sub_5_off_max",
    "SUB_10WTHN_GTON_PPLTN_MIN": "sub_10_on_min", "SUB_10WTHN_GTON_PPLTN_MAX": "sub_10_on_max",
    "SUB_10WTHN_GTOFF_PPLTN_MIN": "sub_10_off_min", "SUB_10WTHN_GTOFF_PPLTN_MAX": "sub_10_off_max",
    "SUB_30WTHN_GTON_PPLTN_MIN": "sub_30_on_min", "SUB_30WTHN_GTON_PPLTN_MAX": "sub_30_on_max",
    "SUB_30WTHN_GTOFF_PPLTN_MIN": "sub_30_off_min", "SUB_30WTHN_GTOFF_PPLTN_MAX": "sub_30_off_max",
    "SUB_ACML_GTON_PPLTN_MIN": "sub_acml_on_min", "SUB_ACML_GTON_PPLTN_MAX": "sub_acml_on_max",
    "SUB_ACML_GTOFF_PPLTN_MIN": "sub_acml_off_min", "SUB_ACML_GTOFF_PPLTN_MAX": "sub_acml_off_max",
}


def text(node, tag):
    if node is None:
        return ""
    found = node.find(tag)
    return (found.text or "").strip() if found is not None else ""


def append_rows(path, cols, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def events_done_today(path):
    """오늘 행사 목록을 이미 저장한 장소 코드 모음"""
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8-sig") as f:
        return {r["area_cd"] for r in csv.DictReader(f)}


def fetch(key, area_cd):
    url = BASE.format(key=key, area=urllib.parse.quote(area_cd))
    with urllib.request.urlopen(url, timeout=30) as resp:
        return ET.fromstring(resp.read())


def parse(root, area_cd, area_nm, collected_at, want_events):
    code = text(root.find("RESULT"), "RESULT.CODE")
    if code and code != "INFO-000":
        raise RuntimeError(f"{code} {text(root.find('RESULT'), 'RESULT.MESSAGE')}")

    city = root.find("CITYDATA")
    live = {"collected_at": collected_at, "area_cd": area_cd, "area_nm": area_nm}

    pp = city.find("LIVE_PPLTN_STTS/LIVE_PPLTN_STTS") if city is not None else None
    live["ppltn_time"] = text(pp, "PPLTN_TIME")
    live["congest_lvl"] = text(pp, "AREA_CONGEST_LVL")
    live["ppltn_min"] = text(pp, "AREA_PPLTN_MIN")
    live["ppltn_max"] = text(pp, "AREA_PPLTN_MAX")

    sub = city.find("LIVE_SUB_PPLTN") if city is not None else None
    for tag, col in SUB_MAP.items():
        live[col] = text(sub, tag)

    fcst = []
    if pp is not None:
        for f in pp.findall("FCST_PPLTN/FCST_PPLTN"):
            fcst.append({
                "collected_at": collected_at, "area_cd": area_cd, "area_nm": area_nm,
                "fcst_time": text(f, "FCST_TIME"),
                "fcst_congest_lvl": text(f, "FCST_CONGEST_LVL"),
                "fcst_ppltn_min": text(f, "FCST_PPLTN_MIN"),
                "fcst_ppltn_max": text(f, "FCST_PPLTN_MAX"),
            })

    events = []
    if want_events and city is not None:
        for e in city.findall("EVENT_STTS/EVENT_STTS"):
            events.append({
                "collected_at": collected_at, "area_cd": area_cd, "area_nm": area_nm,
                "event_nm": text(e, "EVENT_NM"),
                "event_period": text(e, "EVENT_PERIOD"),
                "event_place": text(e, "EVENT_PLACE"),
                "event_x": text(e, "EVENT_X"),
                "event_y": text(e, "EVENT_Y"),
                "event_url": text(e, "URL"),
            })
    return live, fcst, events


def main():
    key = os.environ.get("SEOUL_API_KEY", "").strip()
    if not key:
        sys.exit("환경변수 SEOUL_API_KEY 가 비어 있어요.")

    with open(os.path.join(HERE, "places.csv"), encoding="utf-8") as f:
        places = list(csv.DictReader(f))

    now = datetime.now(KST)
    day = now.strftime("%Y-%m-%d")
    collected_at = now.strftime("%Y-%m-%d %H:%M")
    live_path = os.path.join(DATA, "live", f"{day}.csv")
    fcst_path = os.path.join(DATA, "fcst", f"{day}.csv")
    event_path = os.path.join(DATA, "events", f"{day}.csv")
    done = events_done_today(event_path)

    lives, fcsts, events, fails = [], [], [], []
    for p in places:
        cd, nm = p["area_cd"], p["area_nm"]
        try:
            root = fetch(key, cd)
            live, fc, ev = parse(root, cd, nm, collected_at, cd not in done)
            lives.append(live)
            fcsts.extend(fc)
            events.extend(ev)
        except Exception as e:  # 한 장소가 실패해도 나머지는 계속
            fails.append(f"{nm}: {e}")
            # 인증키 오류(INFO-100, ERROR-300)나 호출 한도 초과(ERROR-337)면 더 부르지 않고 멈춤
            if any(c in str(e) for c in ("ERROR-337", "INFO-100", "ERROR-300")):
                break
        time.sleep(0.3)

    append_rows(live_path, LIVE_COLS, lives)
    append_rows(fcst_path, FCST_COLS, fcsts)
    append_rows(event_path, EVENT_COLS, events)

    print(f"[{collected_at}] 성공 {len(lives)}곳 / 실패 {len(fails)}곳")
    for msg in fails:
        print("  -", msg)
    if not lives:
        sys.exit(1)


if __name__ == "__main__":
    main()

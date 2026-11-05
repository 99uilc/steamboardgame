"""games.json의 앱 ID로 스팀에서 가격/평가/출시일을 가져와 prices.json에 저장합니다."""
import json, re, time, pathlib, datetime, urllib.request

ROOT = pathlib.Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9", "Referer": "https://store.steampowered.com/"}
COOKIE = "l=korean; birthtime=-2211638399; mature_content=1; wants_mature_content=1; lastagecheckage=1-January-1900"
# 평가 문구 -> 코드 (긴 문구부터 검사)
RV_TEXT = [("압도적으로 긍정적", "O"), ("매우 긍정적", "P"), ("대체로 긍정적", "M"), ("긍정적", "G"),
           ("복합적", "X"), ("압도적으로 부정적", "w"), ("매우 부정적", "v"), ("대체로 부정적", "N"), ("부정적", "n")]
SCORE = {9: "O", 8: "P", 7: "G", 6: "M", 5: "X", 4: "N", 3: "n", 2: "v", 1: "w"}
fail = {"scrape": 0, "api": 0}   # 연속 실패 횟수
stat = {"price": 0, "review": 0}


def fetch(url, cookie=False):
    for t in range(2):
        try:
            h = dict(UA, Accept="application/json, text/plain, */*")
            if cookie:
                h["Cookie"] = COOKIE
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            print("재시도:", url, e)
            time.sleep(2)
    return None


def get_json(url):
    txt = fetch(url)
    try:
        return json.loads(txt) if txt else None
    except ValueError:
        print("JSON 아님:", url)
        return None


def digits(s):
    d = re.sub(r"\D", "", s or "")
    return int(d) if d else 0


def iso_date(s):
    m = re.search(r"(\d+)\D+(\d+)\D+(\d+)", s or "")
    return "%04d-%02d-%02d" % tuple(map(int, m.groups())) if m else ""


def parse_store_html(html):
    """상점 페이지 HTML에서 평가 코드를 읽습니다. 페이지가 정상이 아니면 None."""
    if not html or "apphub_AppName" not in html:
        return None
    few = None
    for m in re.finditer(r'class="game_review_summary[^"]*"[^>]*>\s*([^<]+?)\s*</span>', html):
        text = m.group(1)
        if "사용자 평가" in text or "user review" in text:
            n = digits(text)
            few = few or ("u%d" % n if n else "0")
            continue
        for key, code in RV_TEXT:
            if key in text:
                return code
    return few or "0"


def review_from_store(app_id):
    if fail["scrape"] >= 5:
        return None
    code = parse_store_html(fetch(f"https://store.steampowered.com/app/{app_id}/?l=korean", cookie=True))
    fail["scrape"] = 0 if code else fail["scrape"] + 1
    return code


def review_from_api(app_id):
    if fail["api"] >= 5:
        return None
    rv = get_json(f"https://store.steampowered.com/appreviews/{app_id}?json=1&filter=all&language=all&purchase_type=all&num_per_page=0")
    qs = (rv or {}).get("query_summary")
    fail["api"] = 0 if qs else fail["api"] + 1
    if not qs:
        return None
    total, score = qs.get("total_reviews", 0), qs.get("review_score", 0)
    return SCORE.get(score, "0") if total >= 10 and score else ("u%d" % total if total else "0")


def update_one(app_id, old):
    cur = dict(old)
    res = get_json(f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=kr&l=korean")
    node = (res or {}).get(app_id)
    if node and node.get("success"):
        stat["price"] += 1
        data = node["data"]
        rd = data.get("release_date") or {}
        po = data.get("price_overview")
        if rd.get("coming_soon"):
            cur.update(i="S", f=0, c=0, d="")
        else:
            cur["d"] = iso_date(rd.get("date")) or old.get("d", "")
            if po:
                disc = int(po.get("discount_percent") or 0)
                final = digits(po.get("final_formatted"))
                cur.update(i=digits(po.get("initial_formatted")) or final,
                           f=final if disc > 0 else 0, c=disc)
            elif data.get("is_free"):
                cur.update(i="F", f=0, c=0)
            else:
                cur.update(i="U", f=0, c=0)
    code = review_from_store(app_id) or review_from_api(app_id)
    if code:
        cur["rv"] = code
        stat["review"] += 1
    return cur


def main():
    games = json.loads((ROOT / "games.json").read_text(encoding="utf-8"))
    path = ROOT / "prices.json"
    prev = json.loads(path.read_text(encoding="utf-8")).get("items", {}) if path.exists() else {}
    items = {}
    for g in games:
        items[g["id"]] = update_one(g["id"], prev.get(g["id"], {}))
        time.sleep(1.5)
    kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    out = {"updated": kst.strftime("%Y-%m-%d %H:%M"), "items": items}
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"결과: 가격 {stat['price']}/{len(games)}개, 평가 {stat['review']}/{len(games)}개 갱신")


if __name__ == "__main__":
    main()

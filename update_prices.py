"""games.json의 앱 ID로 스팀에서 가격/평가/출시일을 가져와 prices.json에 저장합니다."""
import json, re, time, pathlib, datetime, urllib.request

ROOT = pathlib.Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"}
SCORE = {9: "O", 8: "P", 7: "G", 6: "M", 5: "X", 4: "N", 3: "n", 2: "v", 1: "w"}


def get(url):
    for t in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("재시도:", url, e)
            time.sleep(3 * (t + 1))
    return None


def digits(s):
    d = re.sub(r"\D", "", s or "")
    return int(d) if d else 0


def iso_date(s):
    m = re.search(r"(\d+)\D+(\d+)\D+(\d+)", s or "")
    return "%04d-%02d-%02d" % tuple(map(int, m.groups())) if m else ""


def update_one(app_id, old):
    cur = dict(old)
    res = get(f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=kr&l=korean")
    node = (res or {}).get(app_id)
    if node and node.get("success"):
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
    rv = get(f"https://store.steampowered.com/appreviews/{app_id}?json=1&filter=all&language=all&purchase_type=all")
    qs = (rv or {}).get("query_summary")
    if qs:
        total, score = qs.get("total_reviews", 0), qs.get("review_score", 0)
        cur["rv"] = SCORE.get(score, "0") if total >= 10 and score else ("u%d" % total if total else "0")
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


if __name__ == "__main__":
    main()

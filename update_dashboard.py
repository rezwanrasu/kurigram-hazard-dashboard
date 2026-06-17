"""
=============================================================
  KURIGRAM SITREP DASHBOARD UPDATER — Final Version
  KoboToolbox → index.html → GitHub → Cloudflare

  SETUP:  pip install requests
  USAGE:  python update_dashboard.py

  Form fields reflected:
    - des_typ: select_one
    - rain_hours: integer
    - জমির পরিমান: শতক (all types)
    - ইউনিয়ন: UP_MAP decodes up_1…up_32
    - Gender: sick_men / sick_women (flood, heat, cold, drought)
    - Thunderstorm: thunder_storm_loss
    - Rain Storm: rain_storm_loss
    - data_collector field (named)
=============================================================
"""
import requests, json, sys, os, re
from datetime import datetime

# ── CONFIG ───────────────────────────────────────────────────
API_TOKEN = "47f1457c09e523c388ec399f53abac0c44b0a0f1"
ASSET_UID = "avF5RDb7CE4bDugRdwuBwS"
SERVER    = "kf.kobotoolbox.org"
OUTPUT    = "index.html"
# ─────────────────────────────────────────────────────────────

F_UZ   = "location/uz"
F_UP   = "location/up"
F_DATE = "_submission_time"
F_DES  = "des_typ"
F_GEO  = "__003"
F_NEED = "__006"
F_RESP = "data_collector"

# Flood fields
FL = {
    "villages":   "flood/flood_villages",
    "homes":      "flood/flood_house_damaged",
    "waterlogged":"flood/flood_waterlogged_hh",
    "shelter_hh": "flood/flood_shelter_hh",
    "shelter_cap":"flood/flood_shelter_capacity",
    "road_pts":   "flood/flood_road_pts",
    "agri":       "flood/flood_agri_land",
    "schools":    "flood/flood_school_closed",
    "treated":    "flood/flood_treated",
    "deaths":     "flood/flood_drowning_deaths",
    "fish_pts":   "flood/flood_fish_pts",
    "displaced":  "flood/flood_displaced",
    "sick_men":   "flood/flood_sick_men",
    "sick_women": "flood/flood_sick_women",
}

# Rainfall fields
R = {
    "villages":  "rainfall/rain_villages",
    "agri":      "rainfall/rain_agri_land",
    "homes":     "rainfall/rain_hh_loss",
    "displaced": "rainfall/rain_job_displaced",
    "road_pts":  "rainfall/rain_road_pts",
    "hours":     "rainfall/rain_hours",
}

# Heatwave fields
H = {
    "days":      "heat/heat_days",
    "avg_temp":  "heat/heat_avg_temp",
    "sick_men":  "heat/heat_sick_men",
    "sick_women":"heat/heat_sick_women",
    "treated":   "heat/heat_treated",
    "livestock": "heat/heat_livestock_death",
    "poultry":   "heat/heat_poultry_death",
    "agri":      "heat/heat_agri_land",
    "schools":   "heat/heat_school_closed",
    "displaced": "heat/heat_displaced",
}

# Cold wave fields
C = {
    "days":      "cold/cold_days",
    "avg_temp":  "cold/cold_avg_temp",
    "sick_men":  "cold/cold_sick_men",
    "sick_women":"cold/cold_sick_women",
    "treated":   "cold/cold_treated",
    "livestock": "cold/cold_livestock_death",
    "poultry":   "cold/cold_poultry_death",
    "agri":      "cold/cold_agri_land",
    "schools":   "cold/cold_school_closed",
}

# Drought fields
D = {
    "days":      "drought/drought_days",
    "agri":      "drought/drought_agri_land",
    "treated":   "drought/drought_treated",
    "sick_men":  "drought/drought_sick_men",
    "sick_women":"drought/drought_sick_women",
    "livestock": "drought/drought_livestock_death",
    "poultry":   "drought/drought_poultry_death",
    "schools":   "drought/drought_school_closed",
    "displaced": "drought/drought_displaced",
    "food_hh":   "drought/drought_food_hh",
}

# ── Storm fields ─────────────────────────────────────────────
# thunder_storm = yes/no flag; thunder_loss = text description of loss
# rain_storm    = yes/no flag; rain_storm_loss = text description of loss
# We capture: whether storm occurred (flag) + loss description text
# These are inside the rainfall group
THUNDER_FLAG  = "rainfall/thunder_storm"       # "yes" or "no"
THUNDER_LOSS  = "rainfall/thunder_loss"        # text: loss description
RSTORM_FLAG   = "rainfall/rain_storm"          # "yes" or "no"
RSTORM_LOSS   = "rainfall/rain_storm_loss"     # text: loss description
# Also capture rain_tree (trees fallen) and rain_hh_loss as numeric where possible
RAIN_TREES    = "rainfall/rain_tree"           # integer: trees fallen
# ─────────────────────────────────────────────────────────────

# Union code → Bangla name
UP_MAP = {
    "up_1":"যাত্রাপুর","up_2":"বেলগাছা","up_3":"পোড়াদহ","up_4":"কাঁঠালবাড়ী",
    "up_5":"ঘোগাদহ","up_6":"হাতিয়া","up_7":"উলিপুর","up_8":"বজরা",
    "up_9":"তবকপুর","up_10":"গুনাইগাছ","up_11":"সাহেবের আলগা","up_12":"রামখানা",
    "up_13":"ধর্মপাল","up_14":"রায়গঞ্জ","up_15":"বেরুবাড়ী","up_16":"নুনখাওয়া",
    "up_17":"ভোগডাঙ্গা","up_18":"কচুয়া","up_19":"ছাতনাই","up_20":"রৌমারী",
    "up_21":"যদুরচর","up_22":"বন্দবেড়","up_23":"শিলকূড়ী","up_24":"ভুরুঙ্গামারী",
    "up_25":"পাথরডুবি","up_26":"বলদিয়া","up_27":"তিলাই","up_28":"চর ভুরুঙ্গামারী",
    "up_29":"চিলমারী","up_30":"রানীগঞ্জ","up_31":"অষ্টমীর চর","up_32":"থানাহাট",
}

UZ_MAP = {
    "uz_1":"Kurigram Sadar","uz_2":"Ulipur","uz_3":"Chilmari",
    "uz_4":"Nageshwari","uz_5":"Bhurungamari","uz_6":"Rowmari",
}

DES_CODES = {
    "des_1":"Rainfall","des_2":"Heatwave","des_3":"Cold Wave",
    "des_4":"Drought","des_5":"Flood",
    "des_6":"Thunderstorm","des_7":"Rain Storm",
    "rain":"Rainfall","heat":"Heatwave","cold":"Cold Wave",
    "drought":"Drought","flood":"Flood",
    "thunder":"Thunderstorm","rainstorm":"Rain Storm",
}

def nv(r, key):
    try: return float(r.get(key, 0) or 0)
    except: return 0

def decode_union(raw):
    if not raw: return ""
    return UP_MAP.get(str(raw).strip(), str(raw).strip())

def decode_disaster(raw):
    if not raw: return "Unknown"
    parts = str(raw).strip().split()
    names = []
    for p in parts:
        if p in DES_CODES and DES_CODES[p] not in names:
            names.append(DES_CODES[p])
    return ", ".join(names) if names else raw

def fetch():
    print("\n" + "="*52)
    print("  KURIGRAM SITREP DASHBOARD UPDATER")
    print("="*52)
    print(f"\n🔗 Connecting to KoboToolbox...")
    url = f"https://{SERVER}/api/v2/assets/{ASSET_UID}/data/?format=json&limit=30000"
    try:
        r = requests.get(url, headers={"Authorization": f"Token {API_TOKEN}"}, timeout=60)
    except Exception as e:
        print(f"❌ Connection failed: {e}"); sys.exit(1)
    if r.status_code == 401: print("❌ Wrong API token"); sys.exit(1)
    if r.status_code == 404: print("❌ Wrong Asset UID"); sys.exit(1)
    if r.status_code != 200: print(f"❌ Error {r.status_code}"); sys.exit(1)
    results = r.json().get("results", [])
    print(f"✅ {len(results)} submissions fetched")
    return results

def process(results):
    rows = []
    for rec in results:
        uz_code  = str(rec.get(F_UZ, '') or '')
        des_raw  = str(rec.get(F_DES, '') or '')
        des_name = decode_disaster(des_raw)

        geo = str(rec.get(F_GEO, '') or '')
        lat = lon = None
        if geo and geo not in ('', 'None', '[None, None]'):
            parts = geo.split()
            try: lat, lon = float(parts[0]), float(parts[1])
            except: pass

        homes     = nv(rec, FL["homes"])    + nv(rec, R["homes"])
        agri      = (nv(rec, FL["agri"])    + nv(rec, R["agri"]) +
                     nv(rec, H["agri"])     + nv(rec, C["agri"]) +
                     nv(rec, D["agri"]))
        schools   = (nv(rec, FL["schools"]) + nv(rec, H["schools"]) +
                     nv(rec, C["schools"])  + nv(rec, D["schools"]))
        treated   = (nv(rec, FL["treated"]) + nv(rec, H["treated"]) +
                     nv(rec, C["treated"])  + nv(rec, D["treated"]))
        deaths    = nv(rec, FL["deaths"])
        livestock = (nv(rec, H["livestock"])+ nv(rec, C["livestock"]) +
                     nv(rec, D["livestock"]))
        displaced = (nv(rec, FL["displaced"])+ nv(rec, R["displaced"]) +
                     nv(rec, H["displaced"])+ nv(rec, D["displaced"]))
        sick_men  = (nv(rec, FL["sick_men"])+ nv(rec, H["sick_men"]) +
                     nv(rec, C["sick_men"]) + nv(rec, D["sick_men"]))
        sick_women= (nv(rec, FL["sick_women"])+ nv(rec, H["sick_women"]) +
                     nv(rec, C["sick_women"])+ nv(rec, D["sick_women"]))

        # Storm fields — boolean flags + text loss description
        thunder_occurred = 1 if str(rec.get(THUNDER_FLAG, '') or '').strip().lower() == 'yes' else 0
        thunder_loss_txt = str(rec.get(THUNDER_LOSS, '') or '').strip()
        rstorm_occurred  = 1 if str(rec.get(RSTORM_FLAG, '') or '').strip().lower() == 'yes' else 0
        rstorm_loss_txt  = str(rec.get(RSTORM_LOSS, '') or '').strip()
        rain_trees       = int(nv(rec, RAIN_TREES))

        rows.append({
            "upazila":    UZ_MAP.get(uz_code, uz_code) or "Unknown",
            "union":      decode_union(rec.get(F_UP, '') or ''),
            "date":       str(rec.get(F_DATE, '') or '')[:10],
            "disaster":   des_name,
            "des_raw":    des_raw,
            "lat": lat, "lon": lon,
            "needs":      str(rec.get(F_NEED, '') or '')[:80],
            "respondent": str(rec.get(F_RESP, '') or '').strip(),
            "homes":      int(homes),
            "agri":       round(agri, 1),
            "schools":    int(schools),
            "treated":    int(treated),
            "deaths":     int(deaths),
            "livestock":  int(livestock),
            "displaced":  int(displaced),
            "sick_men":   int(sick_men),
            "sick_women": int(sick_women),
            "thunder":    thunder_occurred,          # 1 if thunderstorm reported
            "thunder_loss": thunder_loss_txt,        # text description
            "rstorm":     rstorm_occurred,           # 1 if rain storm reported
            "rstorm_loss": rstorm_loss_txt,          # text description
            "rain_trees": rain_trees,                # trees fallen (integer)
            "flood_villages": int(nv(rec, FL["villages"])),
            "rain_villages":  int(nv(rec, R["villages"])),
        })

    def sm(k): return sum(r[k] for r in rows)

    kpis = {
        "submissions": len(rows),
        "homes":       int(sm("homes")),
        "agri":        round(sm("agri"), 1),
        "schools":     int(sm("schools")),
        "deaths":      int(sm("deaths")),
        "treated":     int(sm("treated")),
        "livestock":   int(sm("livestock")),
        "displaced":   int(sm("displaced")),
        "sick_men":    int(sm("sick_men")),
        "sick_women":  int(sm("sick_women")),
        "thunder":     int(sm("thunder")),   # count of submissions reporting thunderstorm
        "rstorm":      int(sm("rstorm")),    # count of submissions reporting rain storm
        "rain_trees":  int(sm("rain_trees")),
    }

    print(f"\n📊 Totals — {len(rows)} submissions:")
    for k, v in kpis.items():
        if k != "submissions":
            print(f"   {k:15} {v}")

    # By Upazila
    uz_map = {}
    for r in rows:
        u = r["upazila"]
        if u not in uz_map:
            uz_map[u] = {"name":u,"submissions":0,"homes":0,"agri":0,
                         "schools":0,"deaths":0,"treated":0,"livestock":0,
                         "displaced":0,"sick_men":0,"sick_women":0,
                         "thunder":0,"rstorm":0,"rain_trees":0,
                         "flood_villages":0,"rain_villages":0}
        uz_map[u]["submissions"] += 1
        for k in ["homes","agri","schools","deaths","treated","livestock",
                  "displaced","sick_men","sick_women","thunder","rstorm",
                  "rain_trees","flood_villages","rain_villages"]:
            uz_map[u][k] += r[k]

    # By Disaster
    def has(r, *codes): return any(c in r["des_raw"] for c in codes)
    def dc(*codes):     return sum(1 for r in rows if has(r, *codes))
    def ds(k, *codes):  return sum(r[k] for r in rows if has(r, *codes))

    dis_data = [
        {"name":"Rainfall","bn":"অতিবৃষ্টি","color":"#2563EB",
         "submissions":dc("des_1","rain"),"displaced":ds("displaced","des_1","rain"),
         "agri":round(ds("agri","des_1","rain"),1),"schools":ds("schools","des_1","rain"),
         "treated":ds("treated","des_1","rain"),"livestock":ds("livestock","des_1","rain"),
         "homes":ds("homes","des_1","rain"),"sick_men":0,"sick_women":0,"tstorm":0},

        {"name":"Heatwave","bn":"তাপদাহ","color":"#EA580C",
         "submissions":dc("des_2","heat"),"displaced":ds("displaced","des_2","heat"),
         "agri":round(ds("agri","des_2","heat"),1),"schools":ds("schools","des_2","heat"),
         "treated":ds("treated","des_2","heat"),"livestock":ds("livestock","des_2","heat"),
         "homes":0,"sick_men":ds("sick_men","des_2","heat"),
         "sick_women":ds("sick_women","des_2","heat"),"tstorm":0},

        {"name":"Cold Wave","bn":"শৈত্যপ্রবাহ","color":"#0891B2",
         "submissions":dc("des_3","cold"),"displaced":0,
         "agri":round(ds("agri","des_3","cold"),1),"schools":ds("schools","des_3","cold"),
         "treated":ds("treated","des_3","cold"),"livestock":ds("livestock","des_3","cold"),
         "homes":0,"sick_men":ds("sick_men","des_3","cold"),
         "sick_women":ds("sick_women","des_3","cold"),"tstorm":0},

        {"name":"Drought","bn":"খরা","color":"#B45309",
         "submissions":dc("des_4","drought"),"displaced":ds("displaced","des_4","drought"),
         "agri":round(ds("agri","des_4","drought"),1),"schools":ds("schools","des_4","drought"),
         "treated":ds("treated","des_4","drought"),"livestock":ds("livestock","des_4","drought"),
         "homes":0,"sick_men":ds("sick_men","des_4","drought"),
         "sick_women":ds("sick_women","des_4","drought"),"tstorm":0},

        {"name":"Flood","bn":"বন্যা","color":"#0D9488",
         "submissions":dc("des_5","flood"),"displaced":ds("displaced","des_5","flood"),
         "agri":round(ds("agri","des_5","flood"),1),"schools":ds("schools","des_5","flood"),
         "treated":ds("treated","des_5","flood"),"livestock":0,
         "homes":ds("homes","des_5","flood"),"sick_men":ds("sick_men","des_5","flood"),
         "sick_women":ds("sick_women","des_5","flood"),"tstorm":0},

        {"name":"Thunderstorm","bn":"বজ্রঝড়","color":"#7C3AED",
         "submissions":dc("des_6","thunder"),"displaced":0,
         "agri":0,"schools":0,"treated":0,"livestock":0,
         "homes":ds("tstorm","des_6","thunder"),
         "sick_men":0,"sick_women":0,"tstorm":ds("tstorm","des_6","thunder")},

        {"name":"Rain Storm","bn":"বৃষ্টিঝড়","color":"#0369A1",
         "submissions":dc("des_7","rainstorm"),"displaced":0,
         "agri":0,"schools":0,"treated":0,"livestock":0,
         "homes":ds("rstorm","des_7","rainstorm"),
         "sick_men":0,"sick_women":0,"tstorm":ds("rstorm","des_7","rainstorm")},
    ]

    raw_out = [{
        "date":         r["date"],
        "upazila":      r["upazila"],
        "union":        r["union"],
        "disaster":     r["disaster"][:40],
        "homes":        r["homes"],
        "agri":         r["agri"],
        "deaths":       r["deaths"],
        "treated":      r["treated"],
        "schools":      r["schools"],
        "displaced":    r["displaced"],
        "sick_men":     r["sick_men"],
        "sick_women":   r["sick_women"],
        "thunder":      r["thunder"],
        "thunder_loss": r["thunder_loss"],
        "rstorm":       r["rstorm"],
        "rstorm_loss":  r["rstorm_loss"],
        "rain_trees":   r["rain_trees"],
        "needs":        r["needs"],
        "respondent":   r["respondent"],
        "lat":          r["lat"],
        "lon":          r["lon"],
    } for r in rows]

    return {
        "kpis":      kpis,
        "upazila":   list(uz_map.values()),
        "disaster":  dis_data,
        "raw":       raw_out,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

def update_html(data):
    if not os.path.exists(OUTPUT):
        print(f"❌ {OUTPUT} not found."); sys.exit(1)
    with open(OUTPUT, "r", encoding="utf-8") as f:
        html = f.read()
    # Sanitize string fields to prevent JS syntax errors from special chars
    def sanitize(obj):
        if isinstance(obj, str):
            return obj.replace("\\", "").replace("\r", "").replace("\x00", "")
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(i) for i in obj]
        return obj
    clean_data = sanitize(data)
    new_json = json.dumps(clean_data, ensure_ascii=True, separators=(',', ':'))
    # Target the <script type="application/json"> tag
    html = re.sub(
        r'(<script id="D" type="application/json">).*?(</script>)',
        r'\1\n' + new_json + r'\n\2',
        html, flags=re.DOTALL
    )
    # Fallback: also try old pattern
    if 'const EMBEDDED = ' in html:
        html = re.sub(r"const EMBEDDED = \{.*?\};",
                      f"const EMBEDDED = {new_json};", html, flags=re.DOTALL)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ {OUTPUT} updated")

def main():
    results = fetch()
    data    = process(results)
    update_html(data)
    k = data["kpis"]
    print(f"\n🎉 Done — {k['submissions']} submissions")
    print(f"   Homes:        {k['homes']}")
    print(f"   Agri:         {k['agri']} shotok")
    print(f"   Deaths:       {k['deaths']}")
    print(f"   Treated:      {k['treated']}")
    print(f"   Displaced:    {k['displaced']}")
    print(f"   Male sick:    {k['sick_men']}")
    print(f"   Female sick:  {k['sick_women']}")
    print(f"   Thunderstorm: {k['thunder']} reports")
    print(f"   Rain Storm:   {k['rstorm']} reports")
    print(f"   Trees fallen: {k['rain_trees']}\n")

if __name__ == "__main__":
    main()

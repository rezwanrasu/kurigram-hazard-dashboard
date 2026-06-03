"""
=============================================================
  KURIGRAM SITREP DASHBOARD UPDATER — Final Version
  KoboToolbox → index.html → GitHub → Cloudflare

  USAGE:
    python update_dashboard.py

  SETUP (one time):
    pip install requests

  KoboToolbox form changes reflected here:
    - দূর্যোগের ধরণ (des_typ): now select_one (was select_multiple)
    - কত ঘন্টা বৃষ্টি হয়েছে (rain_hours): now integer (was select_one)
    - জমির পরিমান: unit changed from বিঘা to শতক (all disaster types)
    - ইউনিয়ন: UP_MAP decodes up_1…up_32 codes to Bangla names

  After running:
    Upload index.html to GitHub repository
    GitHub Actions auto-deploys to Cloudflare
=============================================================
"""
import requests, json, sys, os, re
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────
API_TOKEN = "47f1457c09e523c388ec399f53abac0c44b0a0f1"
ASSET_UID = "avF5RDb7CE4bDugRdwuBwS"
SERVER    = "kf.kobotoolbox.org"
OUTPUT    = "index.html"
# ────────────────────────────────────────────────────────────

# Exact field names confirmed from KoboToolbox API
F_UZ   = "location/uz"
F_UP   = "location/up"
F_DATE = "_submission_time"
F_DES  = "des_typ"
F_GEO  = "__003"
F_NEED = "__006"
F_RESP = "__007"

# Flood fields
FL = {
    "villages":    "flood/flood_villages",
    "homes":       "flood/flood_house_damaged",
    "waterlogged": "flood/flood_waterlogged_hh",
    "shelter_hh":  "flood/flood_shelter_hh",
    "shelter_cap": "flood/flood_shelter_capacity",
    "road_pts":    "flood/flood_road_pts",
    "agri":        "flood/flood_agri_land",
    "schools":     "flood/flood_school_closed",
    "treated":     "flood/flood_treated",
    "deaths":      "flood/flood_drowning_deaths",
    "fish_pts":    "flood/flood_fish_pts",
    "displaced":   "flood/flood_displaced",
}

# Rainfall fields (কত ঘন্টা বৃষ্টি হয়েছে is now an integer field in KoboToolbox)
R = {
    "villages":  "rainfall/rain_villages",
    "agri":      "rainfall/rain_agri_land",
    "homes":     "rainfall/rain_hh_loss",
    "displaced": "rainfall/rain_job_displaced",
    "road_pts":  "rainfall/rain_road_pts",
    "hours":     "rainfall/rain_hours",   # integer (was select_one)
}

# Heatwave fields
H = {
    "days":      "heat/heat_days",
    "avg_temp":  "heat/heat_avg_temp",
    "sick":      "heat/heat_sick_people",
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
    "sick":      "cold/cold_sick_people",
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
    "livestock": "drought/drought_livestock_death",
    "poultry":   "drought/drought_poultry_death",
    "schools":   "drought/drought_school_closed",
    "displaced": "drought/drought_displaced",
    "food_hh":   "drought/drought_food_hh",
}

# Union code → display name (ইউনিয়ন কোড → নাম)
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

def decode_union(raw):
    if not raw: return ""
    return UP_MAP.get(str(raw).strip(), str(raw).strip())
UZ_MAP = {
    "uz_1":"Kurigram Sadar","uz_2":"Ulipur","uz_3":"Chilmari",
    "uz_4":"Nageshwari","uz_5":"Bhurungamari","uz_6":"Rowmari",
}

# Disaster code → name
DES_CODES = {
    "des_1":"Rainfall","des_2":"Heatwave","des_3":"Cold Wave",
    "des_4":"Drought","des_5":"Flood",
    "rain":"Rainfall","heat":"Heatwave","cold":"Cold Wave",
    "drought":"Drought","flood":"Flood",
}

def nv(r, key):
    try: return float(r.get(key, 0) or 0)
    except: return 0

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

        # Parse geopoint
        geo = str(rec.get(F_GEO, '') or '')
        lat = lon = None
        if geo and geo not in ('', 'None', '[None, None]'):
            parts = geo.split()
            try: lat, lon = float(parts[0]), float(parts[1])
            except: pass

        # Compute totals
        homes     = nv(rec, FL["homes"])     + nv(rec, R["homes"])
        agri      = (nv(rec, FL["agri"])     + nv(rec, R["agri"]) +
                     nv(rec, H["agri"])      + nv(rec, C["agri"]) +
                     nv(rec, D["agri"]))
        schools   = (nv(rec, FL["schools"])  + nv(rec, H["schools"]) +
                     nv(rec, C["schools"])   + nv(rec, D["schools"]))
        treated   = (nv(rec, FL["treated"])  + nv(rec, H["treated"]) +
                     nv(rec, C["treated"])   + nv(rec, D["treated"]))
        deaths    = nv(rec, FL["deaths"])
        livestock = (nv(rec, H["livestock"]) + nv(rec, C["livestock"]) +
                     nv(rec, D["livestock"]))
        displaced = (nv(rec, FL["displaced"])+ nv(rec, R["displaced"]) +
                     nv(rec, H["displaced"]) + nv(rec, D["displaced"]))

        rows.append({
            "upazila":        UZ_MAP.get(uz_code, uz_code) or "Unknown",
            "union":          decode_union(rec.get(F_UP, '') or ''),
            "date":           str(rec.get(F_DATE, '') or '')[:10],
            "disaster":       des_name,
            "des_raw":        des_raw,
            "lat":            lat,
            "lon":            lon,
            "needs":          str(rec.get(F_NEED, '') or '')[:80],
            "respondent":     str(rec.get(F_RESP, '') or ''),
            "homes":          int(homes),
            "agri":           round(agri, 1),
            "schools":        int(schools),
            "treated":        int(treated),
            "deaths":         int(deaths),
            "livestock":      int(livestock),
            "displaced":      int(displaced),
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
    }

    print(f"\n📊 Totals across all {len(rows)} submissions:")
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
                         "displaced":0,"flood_villages":0,"rain_villages":0}
        uz_map[u]["submissions"] += 1
        for k in ["homes","agri","schools","deaths","treated",
                  "livestock","displaced","flood_villages","rain_villages"]:
            uz_map[u][k] += r[k]

    # By Disaster
    def has(r, *codes):
        return any(c in r["des_raw"] for c in codes)
    def dc(*codes):   return sum(1 for r in rows if has(r, *codes))
    def dsum(k,*codes): return sum(r[k] for r in rows if has(r, *codes))

    dis_data = [
        {"name":"Rainfall","bn":"অতিবৃষ্টি","color":"#2563EB",
         "submissions":dc("des_1","rain"),
         "displaced":dsum("displaced","des_1","rain"),
         "agri":round(dsum("agri","des_1","rain"),1),
         "schools":dsum("schools","des_1","rain"),
         "treated":dsum("treated","des_1","rain"),
         "livestock":dsum("livestock","des_1","rain"),
         "homes":dsum("homes","des_1","rain")},

        {"name":"Heatwave","bn":"তাপদাহ","color":"#EA580C",
         "submissions":dc("des_2","heat"),
         "displaced":dsum("displaced","des_2","heat"),
         "agri":round(dsum("agri","des_2","heat"),1),
         "schools":dsum("schools","des_2","heat"),
         "treated":dsum("treated","des_2","heat"),
         "livestock":dsum("livestock","des_2","heat"),
         "homes":0},

        {"name":"Cold Wave","bn":"শৈত্যপ্রবাহ","color":"#0891B2",
         "submissions":dc("des_3","cold"),
         "displaced":0,
         "agri":round(dsum("agri","des_3","cold"),1),
         "schools":dsum("schools","des_3","cold"),
         "treated":dsum("treated","des_3","cold"),
         "livestock":dsum("livestock","des_3","cold"),
         "homes":0},

        {"name":"Drought","bn":"খরা","color":"#B45309",
         "submissions":dc("des_4","drought"),
         "displaced":dsum("displaced","des_4","drought"),
         "agri":round(dsum("agri","des_4","drought"),1),
         "schools":dsum("schools","des_4","drought"),
         "treated":dsum("treated","des_4","drought"),
         "livestock":dsum("livestock","des_4","drought"),
         "homes":0},

        {"name":"Flood","bn":"বন্যা","color":"#0D9488",
         "submissions":dc("des_5","flood"),
         "displaced":dsum("displaced","des_5","flood"),
         "agri":round(dsum("agri","des_5","flood"),1),
         "schools":dsum("schools","des_5","flood"),
         "treated":dsum("treated","des_5","flood"),
         "livestock":0,
         "homes":dsum("homes","des_5","flood")},
    ]

    raw_out = [{
        "date":       r["date"],
        "upazila":    r["upazila"],
        "union":      r["union"],
        "disaster":   r["disaster"][:40],
        "homes":      r["homes"],
        "agri":       r["agri"],
        "deaths":     r["deaths"],
        "treated":    r["treated"],
        "schools":    r["schools"],
        "displaced":  r["displaced"],
        "needs":      r["needs"],
        "respondent": r["respondent"],
        "lat":        r["lat"],
        "lon":        r["lon"],
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
        print(f"❌ {OUTPUT} not found in this folder.")
        print(f"   Make sure {OUTPUT} is in the same folder as this script.")
        sys.exit(1)
    with open(OUTPUT, "r", encoding="utf-8") as f:
        html = f.read()
    new_data = f"const EMBEDDED = {json.dumps(data, ensure_ascii=False)};"
    html = re.sub(r"const EMBEDDED = \{.*?\};", new_data, html, flags=re.DOTALL)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ {OUTPUT} updated with live data")

def main():
    results = fetch()
    data    = process(results)
    update_html(data)
    k = data["kpis"]
    print(f"\n🎉 Dashboard ready — {k['submissions']} submissions")
    print(f"   Homes Damaged:   {k['homes']}")
    print(f"   Agri Land:       {k['agri']} shotok")
    print(f"   Schools Closed:  {k['schools']}")
    print(f"   Deaths:          {k['deaths']}")
    print(f"   People Treated:  {k['treated']}")
    print(f"   Displaced:       {k['displaced']}")
    print(f"\n👉 Upload {OUTPUT} to GitHub to update live dashboard\n")

if __name__ == "__main__":
    main()

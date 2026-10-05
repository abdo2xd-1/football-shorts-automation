import subprocess
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# استبعاد ألعاب الفيديو والمحاكاة نهائياً
BANNED_KEYWORDS = [
    "fifa", "pes", "efootball", "fc 24", "fc 25", "fc 26", "ps5", "ps4",
    "gameplay", "mod", "simulation", "محاكاة", "بلايستيشن", "بيس", "فيفا"
]

# كلمات بحث محصورة لبطولات المنتخبات الوطنية فقط
INTERNATIONAL_QUERIES = [
    "ملخص دوري الأمم الأوروبية اليوم",
    "UEFA Nations League highlights today",
    "ملخص تصفيات كأس العالم اليوم",
    "ملخص تصفيات أمم أفريقيا اليوم",
    "AFCON qualifiers highlights today",
    "ملخص مباريات دولية ودية اليوم",
    "ملخص مباراة منتخب مصر اليوم",
    "ملخص مباراة منتخب المغرب اليوم",
    "ملخص مباراة البرتغال اليوم",
    "ملخص مباراة إسبانيا اليوم",
    "ملخص مباراة ألمانيا اليوم",
    "ملخص مباراة فرنسا اليوم"
]

def is_valid_match(title: str, duration: int) -> bool:
    t_lower = title.lower()
    for ban in BANNED_KEYWORDS:
        if ban in t_lower:
            return False
            
    # مدة ملخص واقعي بين 2 إلى 25 دقيقة
    if not (120 <= duration <= 1500):
        return False
        
    return True

def find_national_matches():
    print("🌍 بدء البحث عن أحدث مباريات المنتخبات الوطنية المنشورة اليوم...")
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    date_filter = yesterday.strftime("%Y%m%d")

    found_videos = []

    for query in INTERNATIONAL_QUERIES:
        print(f"🔍 فحص: '{query}'...")
        cmd = [
            "yt-dlp",
            f"ytsearch8:{query}",
            "--dateafter", date_filter,
            "--dump-json",
            "--flat-playlist",
            "--no-warnings"
        ]
        
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            continue
            
        for line in res.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                item = json.loads(line)
                vid_id = item.get("id")
                title = item.get("title", "")
                duration = item.get("duration", 0) or 0

                if is_valid_match(title, duration):
                    url = f"https://www.youtube.com/watch?v={vid_id}"
                    if not any(v["url"] == url for v in found_videos):
                        found_videos.append({"url": url, "title": title})
                        print(f"✅ تم التقاط مباراة منتخب: {title}")
                        if len(found_videos) >= 1:
                            return found_videos[0]["url"], found_videos[0]["title"]
            except Exception:
                continue

    if found_videos:
        return found_videos[0]["url"], found_videos[0]["title"]
    return None, None

if __name__ == "__main__":
    url, title = find_national_matches()
    if url:
        with open("target_match.txt", "w", encoding="utf-8") as f:
            f.write(f"{url}\n{title}")
        print(f"TARGET_FOUND: {url}")
    else:
        print("NO_TARGETS_FOUND")

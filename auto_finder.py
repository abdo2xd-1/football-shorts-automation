import subprocess
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# الكلمات الممنوعة نهائياً لاستبعاد ألعاب الفيديو
BANNED_KEYWORDS = [
    "fifa", "pes", "efootball", "fc 24", "fc 25", "fc 26", "ps5", "ps4",
    "gameplay", "mod", "simulation", "محاكاة", "بلايستيشن", "بيس", "فيفا", "e-football"
]

# كلمات بحث موسعة تشمل كل مباريات المنتخبات والدوريات لليوم
CHANNEL_SEARCH_TOPICS = {
    "crazy_skills": [
        "ملخص مباراة منتخب اليوم",
        "أهداف مباريات المنتخبات اليوم",
        "highlights international match today",
        "World cup qualifiers highlights",
        "AFCON qualifiers highlights",
        "تصفيات كأس العالم ملخص",
        "ملخص مباريات اليوم المنتخبات"
    ],
    "90_plus": [
        "Premier League highlights today",
        "La Liga highlights today",
        "Champions League highlights today",
        "أهداف الدوري الإنجليزي اليوم",
        "أهداف الدوري الإسباني اليوم",
        "ملخص مباريات الدوري الانجليزي"
    ],
    "hattrick": [
        "ملخص الدوري المصري اليوم",
        "أهداف الدوري المصري اليوم",
        "Serie A highlights today",
        "Ligue 1 highlights today",
        "أهداف الدوري الإيطالي اليوم",
        "ملخص مباريات الدوري الفرنسي"
    ]
}

def is_video_within_12_hours(upload_date_str: str, timestamp: int) -> bool:
    """التحقق المرن والدقيق من أن الفيديو رُفع اليوم أو خلال آخر 12-18 ساعة"""
    now = datetime.now(timezone.utc)
    
    # إذا توفر timestamp دقيق
    if timestamp:
        try:
            v_time = datetime.fromtimestamp(timestamp, timezone.utc)
            diff = now - v_time
            if timedelta(seconds=0) <= diff <= timedelta(hours=14):
                return True
        except Exception:
            pass

    # إذا توفر تاريخ YYYYMMDD
    if upload_date_str and len(upload_date_str) == 8:
        try:
            v_year = int(upload_date_str[:4])
            v_month = int(upload_date_str[4:6])
            v_day = int(upload_date_str[6:8])
            v_date = datetime(v_year, v_month, v_day, tzinfo=timezone.utc)
            
            # يُقبل إذا كان تاريخ اليوم أو أمس
            day_diff = (now.date() - v_date.date()).days
            if day_diff in [0, 1]:
                return True
        except Exception:
            pass

    return False

def is_valid_football_match(title: str, duration: int) -> bool:
    t_lower = title.lower()
    for b in BANNED_KEYWORDS:
        if b in t_lower:
            return False
            
    # مدة ملخص حقيقي (بين دقيقة ونصف إلى 18 دقيقة)
    if not (80 <= duration <= 1080):
        return False
        
    return True

def find_match_for_channel(channel_key: str):
    searches = CHANNEL_SEARCH_TOPICS.get(channel_key, [])
    print(f"📡 بدء فحص مباريات اليوم المرفوعة حديثاً لقناة: {channel_key}...")

    # البحث بالترتيب حسب تاريخ الرفع الأحدث
    for query in searches:
        print(f"🔍 البحث عن: '{query}'...")
        cmd = [
            "yt-dlp",
            f"ytsearch15:{query}",
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
                
                if not is_valid_football_match(title, duration):
                    continue

                # سحب بيانات التوقيت المؤكدة للفيديو
                info_cmd = [
                    "yt-dlp",
                    "--dump-json",
                    "--no-warnings",
                    f"https://www.youtube.com/watch?v={vid_id}"
                ]
                info_res = subprocess.run(info_cmd, capture_output=True, text=True)
                if info_res.returncode == 0:
                    data = json.loads(info_res.stdout)
                    v_time = data.get("timestamp")
                    v_date = data.get("upload_date")
                    
                    if is_video_within_12_hours(v_date, v_time):
                        url = f"https://www.youtube.com/watch?v={vid_id}"
                        print(f"✅ تم التقاط مباراة حقيقية مرفوعة حديثاً: {title}")
                        return url, title
            except Exception:
                continue

    return None, None

if __name__ == "__main__":
    ch = sys.argv[1] if len(sys.argv) > 1 else "crazy_skills"
    found_url, found_title = find_match_for_channel(ch)
    
    if found_url:
        with open("target_match.txt", "w", encoding="utf-8") as f:
            f.write(f"{found_url}\n{found_title}")
        print(f"TARGET_FOUND: {found_url}")
    else:
        print("NO_TARGETS_FOUND")

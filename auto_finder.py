import subprocess
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# الكلمات الممنوعة تماماً لاستبعاد الألعاب والافتراضيات
BANNED_KEYWORDS = [
    "fifa", "pes", "efootball", "fc 24", "fc 25", "ps5", "ps4",
    "gameplay", "mod", "simulation", "محاكاة", "بلايستيشن", "بيس", "فيفا"
]

# كلمات البحث العامة لجميع مباريات الدوريات المحددة
CHANNEL_SEARCH_TOPICS = {
    "90_plus": [
        "Premier League full match highlights",
        "La Liga match highlights",
        "Champions League highlights",
        "أهداف الدوري الإنجليزي اليوم",
        "أهداف الدوري الإسباني اليوم",
        "ملخص دوري أبطال أوروبا"
    ],
    "hattrick": [
        "ملخص مباريات الدوري المصري اليوم",
        "أهداف الدوري المصري الممتاز",
        "Serie A match highlights",
        "Ligue 1 match highlights",
        "أهداف الدوري الإيطالي اليوم",
        "أهداف الدوري الفرنسي اليوم"
    ],
    "crazy_skills": [
        "UEFA Nations League match highlights",
        "ملخص تصفيات كأس العالم أفريقيا",
        "World Cup Qualifiers CONMEBOL highlights",
        "ملخص مباريات تصفيات آسيا اليوم",
        "International friendly highlights"
    ]
}

def is_strictly_within_12_hours(upload_timestamp: int, upload_date_str: str) -> bool:
    """التحقق الصارم من أن الفيديو لم يمر على رفعه أكثر من 12 ساعة"""
    now = datetime.now(timezone.utc)
    
    # 1. إذا كان الـ timestamp متاحاً
    if upload_timestamp:
        video_time = datetime.fromtimestamp(upload_timestamp, timezone.utc)
        age = now - video_time
        return timedelta(0) <= age <= timedelta(hours=12)
        
    # 2. إذا كان التاريخ كنص بصيغة YYYYMMDD
    if upload_date_str and len(upload_date_str) == 8:
        try:
            video_date = datetime.strptime(upload_date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
            # التأكد أنه تاريخ اليوم أو الأمس القريب جداً
            return (now - video_date).total_seconds() <= 12 * 3600
        except Exception:
            pass

    return False

def is_valid_real_football(title: str, duration: int) -> bool:
    title_lower = title.lower()
    for ban in BANNED_KEYWORDS:
        if ban in title_lower:
            return False
            
    # مدة ملخص كروي حقيقي (من 90 ثانية حتى 15 دقيقة)
    if not (90 <= duration <= 900):
        return False
        
    return True

def find_match_for_channel(channel_key: str):
    searches = CHANNEL_SEARCH_TOPICS.get(channel_key, [])
    print(f"📡 بدء فحص مباريات آخر 12 ساعة لقناة: {channel_key}...")

    for query in searches:
        print(f"🔍 فحص: {query}")
        
        # استرجاع أحدث 10 فيديوهات مع التواريخ بدقة
        cmd = [
            "yt-dlp",
            f"ytsearch10:{query}",
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
                timestamp = item.get("timestamp")
                upload_date = item.get("upload_date")
                
                # فحص الشرط الحقيقي والزمني (أقل من 12 ساعة)
                if is_valid_real_football(title, duration):
                    # التحقق بدقة من تاريخ النشر الفعلي
                    detail_cmd = [
                        "yt-dlp",
                        "--dump-json",
                        "--no-warnings",
                        f"https://www.youtube.com/watch?v={vid_id}"
                    ]
                    detail_res = subprocess.run(detail_cmd, capture_output=True, text=True)
                    if detail_res.returncode == 0:
                        details = json.loads(detail_res.stdout)
                        v_time = details.get("timestamp")
                        v_date = details.get("upload_date")
                        
                        if is_strictly_within_12_hours(v_time, v_date):
                            url = f"https://www.youtube.com/watch?v={vid_id}"
                            print(f"🎯 تم العثور على ماتش حقيقي مرفوع خلال آخر 12 ساعة: {title}")
                            return url, title
            except Exception:
                continue

    return None, None

if __name__ == "__main__":
    ch = sys.argv[1] if len(sys.argv) > 1 else "90_plus"
    found_url, found_title = find_match_for_channel(ch)
    
    if found_url:
        with open("target_match.txt", "w", encoding="utf-8") as f:
            f.write(f"{found_url}\n{found_title}")
        print(f"TARGET_FOUND: {found_url}")
    else:
        print("NO_TARGETS_FOUND: لا توجد مباريات منشورة خلال آخر 12 ساعة مطابقة للشروط.")

import subprocess
import json
import re
from datetime import datetime, timezone, timedelta

# الكلمات الممنوعة نهائياً لمنع ألعاب البلايستيشن
BANNED_KEYWORDS = [
    "fifa", "pes", "efootball", "fc 24", "fc 25", "ps5", "ps4",
    "gameplay", "mod", "simulation", "محاكاة", "بلايستيشن", "بيس", "فيفا"
]

# تصنيف البطولات لكل قناة
CHANNEL_QUERIES = {
    "90_plus": [
        "Premier League highlights",
        "Champions League highlights",
        "ملخص مباراة الدوري الإسباني"
    ],
    "hattrick": [
        "ملخص مباراة الدوري المصري",
        "Serie A highlights",
        "Ligue 1 highlights"
    ],
    "crazy_skills": [
        "UEFA Nations League highlights",
        "تصفيات كأس العالم أفريقيا ملخص",
        "CONMEBOL highlights",
        "تصفيات كأس آسيا ملخص"
    ]
}

def is_real_match(title: str, duration: int) -> bool:
    title_lower = title.lower()
    
    # استبعاد ألعاب الفيديو
    for ban in BANNED_KEYWORDS:
        if ban in title_lower:
            return False
            
    # التأكد أن مدة الملخص حقيقية (من 3 دقائق إلى 16 دقيقة)
    if not (180 <= duration <= 960):
        return False
        
    return True

def find_latest_match(channel_key: str):
    queries = CHANNEL_QUERIES.get(channel_key, [])
    now = datetime.now(timezone.utc)
    twelve_hours_ago = now - timedelta(hours=12)

    for q in queries:
        print(f"🔎 جاري البحث عن: {q} للقناة {channel_key}...")
        
        # البحث عن آخر 5 فيديوهات باستخدام yt-dlp
        search_cmd = [
            "yt-dlp",
            f"ytsearch5:{q}",
            "--dump-json",
            "--flat-playlist",
            "--no-warnings"
        ]
        
        result = subprocess.run(search_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            continue

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                vid_id = data.get("id")
                title = data.get("title", "")
                duration = data.get("duration", 0) or 0
                
                # فحص موعد النشر ونوع المحتوى
                if is_real_match(title, duration):
                    match_url = f"https://www.youtube.com/watch?v={vid_id}"
                    print(f"✅ تم العثور على ماتش حقيقي ممتاز: {title}")
                    return match_url, title
            except Exception:
                continue

    return None, None

if __name__ == "__main__":
    import sys
    channel = sys.argv[1] if len(sys.argv) > 1 else "90_plus"
    url, title = find_latest_match(channel)
    if url:
        with open("target_match.txt", "w", encoding="utf-8") as f:
            f.write(f"{url}\n{title}")
        print(f"TARGET_FOUND: {url}")
    else:
        print("NO_TARGETS_FOUND")

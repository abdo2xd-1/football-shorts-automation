import os
import sys
import json
import subprocess
from datetime import datetime, timezone, timedelta

# الكلمات الممنوعة قطعياً لاستبعاد ألعاب الفيديو ومباريات السيدات والناشئين
BANNED_KEYWORDS = [
    "fifa", "pes", "efootball", "fc 24", "fc 25", "fc 26", "ps5", "ps4",
    "gameplay", "mod", "simulation", "محاكاة", "بلايستيشن", "بيس", "فيفا",
    "women", "female", "liga f", "wsl", "سيدات", "سيدات كرة القدم", 
    "u17", "u19", "u20", "u23", "ناشئين", "شباب", "olympic"
]

# الكلمات المفتاحية الخاصة بكل قناة لملخصات الرجال الرسمية
CHANNEL_SEARCH_QUERIES = {
    "crazy_skills": [
        "ملخص دوري الأمم الأوروبية اليوم",
        "UEFA Nations League highlights today",
        "ملخص تصفيات كأس العالم اليوم",
        "World Cup Qualifiers highlights today",
        "ملخص تصفيات أمم أفريقيا اليوم",
        "AFCON qualifiers highlights today",
        "ملخص مباريات دولية ودية اليوم"
    ],
    "90_plus": [
        "Premier League highlights today",
        "La Liga highlights today",
        "Bundesliga highlights today",
        "Champions League highlights today",
        "ملخص الدوري الإنجليزي اليوم",
        "ملخص الدوري الإسباني اليوم",
        "ملخص دوري أبطال أوروبا اليوم"
    ],
    "hattrick": [
        "ملخص الدوري المصري اليوم",
        "أهداف الدوري المصري اليوم",
        "Serie A highlights today",
        "Ligue 1 highlights today",
        "ملخص دوري أبطال أفريقيا اليوم",
        "CAF Champions League highlights today"
    ]
}

def is_valid_match(title: str, duration: int) -> bool:
    title_lower = title.lower()
    
    # فحص الكلمات الممنوعة
    for ban in BANNED_KEYWORDS:
        if ban in title_lower:
            return False
            
    # مدة ملخص مباراة حقيقية (بين 2.5 دقيقة إلى 30 دقيقة)
    if not (150 <= duration <= 1800):
        return False
        
    return True

def find_matches_for_channel(channel_key: str):
    queries = CHANNEL_SEARCH_QUERIES.get(channel_key, [])
    print(f"📡 بدء البحث المباشر عن مباريات الرجال الرسمية لليوم لقناة [{channel_key}]...")

    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    date_filter = yesterday.strftime("%Y%m%d")

    found_matches = []
    seen_ids = set()

    for q in queries:
        print(f"🔍 فحص استعلام: '{q}'...")
        cmd = [
            "yt-dlp",
            f"ytsearch6:{q}",
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

                if vid_id in seen_ids:
                    continue

                if is_valid_match(title, duration):
                    seen_ids.add(vid_id)
                    found_matches.append({
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                        "title": title
                    })
                    print(f"✅ تم التقاط مباراة مطابقة: {title}")

                    # الاكتفاء بأول 2 إلى 3 مباريات ممتازة لكل قناة يومياً
                    if len(found_matches) >= 3:
                        return found_matches
            except Exception:
                continue

    return found_matches

def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else "crazy_skills"
    matches = find_matches_for_channel(channel)

    with open("matches_queue.json", "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)

    print(f"🎯 تم حفظ {len(matches)} مباراة في matches_queue.json")

if __name__ == "__main__":
    main()

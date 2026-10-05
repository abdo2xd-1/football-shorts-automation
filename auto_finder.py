import subprocess
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# الكلمات الممنوعة قطعياً لاستبعاد ألعاب الفيديو والمحاكاة
BANNED_KEYWORDS = [
    "fifa", "pes", "efootball", "fc 24", "fc 25", "fc 26", "ps5", "ps4",
    "gameplay", "mod", "simulation", "محاكاة", "بلايستيشن", "بيس", "فيفا", "e-football"
]

# قاموس شامل لكافة البطولات الرسمية المقسمة على القنوات الثلاث
CHANNEL_DATABASE = {
    # 1. قناة كبار أوروبا وبطولات العالم للأندية
    "90_plus": [
        # إنجلترا
        "ملخص الدوري الإنجليزي اليوم", "Premier League highlights today",
        "ملخص كأس الاتحاد الإنجليزي", "FA Cup highlights today",
        "ملخص كأس الرابطة الإنجليزية", "Carabao Cup highlights today",
        "ملخص الدرع الخيرية", "Community Shield highlights",
        # إسبانيا
        "ملخص الدوري الإسباني اليوم", "La Liga highlights today",
        "ملخص كأس ملك إسبانيا", "Copa del Rey highlights today",
        "ملخص السوبر الإسباني", "Supercopa de Espana highlights",
        # ألمانيا
        "ملخص الدوري الألماني اليوم", "Bundesliga highlights today",
        "ملخص كأس ألمانيا", "DFB-Pokal highlights today",
        "ملخص السوبر الألماني", "DFL-Supercup highlights",
        # بطولات أندية أوروبا والعالم
        "ملخص دوري أبطال أوروبا اليوم", "Champions League highlights today",
        "ملخص الدوري الأوروبي اليوم", "Europa League highlights today",
        "ملخص دوري المؤتمر الأوروبي", "Conference League highlights",
        "ملخص السوبر الأوروبي", "UEFA Super Cup highlights",
        "ملخص كأس العالم للأندية", "FIFA Club World Cup highlights",
        "ملخص كأس القارات للأندية", "FIFA Intercontinental Cup highlights"
    ],

    # 2. الدوري المصري والبطولات الأفريقية والدوريات التكتيكية (إيطاليا وفرنسا)
    "hattrick": [
        # مصر
        "ملخص الدوري المصري اليوم", "ملخص أهداف الدوري المصري الممتاز",
        "ملخص كأس مصر اليوم", "Egypt Cup highlights",
        "ملخص السوبر المصري", "Egyptian Super Cup highlights",
        "ملخص كأس رابطة الأندية المصرية", "EPL Cup Egypt highlights",
        # بطولات أفريقيا للأندية
        "ملخص دوري أبطال أفريقيا اليوم", "CAF Champions League highlights today",
        "ملخص كأس الكونفيدرالية اليوم", "CAF Confederation Cup highlights",
        "ملخص كأس السوبر الأفريقي", "CAF Super Cup highlights",
        "ملخص الدوري الأفريقي", "African Football League highlights",
        # إيطاليا
        "ملخص الدوري الإيطالي اليوم", "Serie A highlights today",
        "ملخص كأس إيطاليا", "Coppa Italia highlights today",
        "ملخص السوبر الإيطالي", "Supercoppa Italiana highlights",
        # فرنسا
        "ملخص الدوري الفرنسي اليوم", "Ligue 1 highlights today",
        "ملخص كأس فرنسا", "Coupe de France highlights",
        "ملخص كأس الأبطال الفرنسي", "Trophee des Champions highlights"
    ],

    # 3. كافة بطولات المنتخبات الوطنية القارية والدولية
    "crazy_skills": [
        # أوروبا
        "ملخص دوري الأمم الأوروبية اليوم", "UEFA Nations League highlights today",
        "ملخص كأس الأمم الأوروبية", "UEFA Euro highlights",
        "تصفيات أوروبا لكأس العالم ملخص", "European Qualifiers highlights today",
        # أفريقيا
        "ملخص كأس الأمم الأفريقية", "AFCON highlights",
        "ملخص تصفيات كأس العالم أفريقيا اليوم", "African World Cup Qualifiers highlights",
        "ملخص بطولة أمم أفريقيا للمحليين", "CHAN highlights",
        # أمريكا الجنوبية والشمالية
        "ملخص كوبا أمريكا", "Copa America highlights",
        "ملخص تصفيات كأس العالم أمريكا الجنوبية", "CONMEBOL qualifiers highlights",
        "ملخص الكأس الذهبية", "CONCACAF Gold Cup highlights",
        "ملخص دوري أمم الكونكاكاف", "CONCACAF Nations League highlights",
        # آسيا
        "ملخص كأس آسيا", "AFC Asian Cup highlights",
        "ملخص تصفيات كأس العالم آسيا اليوم", "Asian Qualifiers highlights today",
        # العالمية للمنتخبات
        "ملخص كأس العالم", "FIFA World Cup highlights",
        "ملخص الفيناليسيما", "Finalissima highlights",
        "ملخص مباريات دولية ودية اليوم", "International friendly highlights today"
    ]
}

def is_valid_football_match(title: str, duration: int) -> bool:
    t_lower = title.lower()
    for b in BANNED_KEYWORDS:
        if b in t_lower:
            return False
            
    # قبول الملخصات الواقعية حتى 35 دقيقة لتشمل التغطيات الرسمية الموسعة
    if not (60 <= duration <= 2100):
        return False
        
    return True

def find_match_for_channel(channel_key: str):
    searches = CHANNEL_DATABASE.get(channel_key, [])
    print(f"📡 بدء فحص مباريات اليوم المرفوعة حديثاً لقناة: {channel_key}...")

    # فلترة تاريخ اليوم وأمس
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    date_filter = yesterday.strftime("%Y%m%d")

    for query in searches:
        print(f"🔍 البحث عن: '{query}'...")
        
        # استعلام فرز الأحدث مع فلتر التاريخ
        cmd = [
            "yt-dlp",
            f"ytsearch10:{query}",
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

                if is_valid_football_match(title, duration):
                    url = f"https://www.youtube.com/watch?v={vid_id}"
                    print(f"✅ تم التقاط مباراة حقيقية بنجاح: {title}")
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

import os
import sys
import json
import subprocess
import requests
from datetime import datetime, timezone, timedelta

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# القوائم الافتراضية للفرق والمنتخبات عند تعذر الوصول لـ Gemini
FALLBACK_TARGETS = {
    "crazy_skills": [
        {"teams": "المغرب ضد مالي", "tournament": "تصفيات أمم أفريقيا"},
        {"teams": "البرتغال ضد بولندا", "tournament": "دوري الأمم الأوروبية"},
        {"teams": "إسبانيا ضد صربيا", "tournament": "دوري الأمم الأوروبية"},
        {"teams": "مصر ضد جنوب أفريقيا", "tournament": "مباراة ودية دولية"}
    ],
    "90_plus": [
        {"teams": "Arsenal vs Chelsea", "tournament": "Premier League"},
        {"teams": "Real Madrid vs Barcelona", "tournament": "La Liga"},
        {"teams": "Bayern Munich vs Dortmund", "tournament": "Bundesliga"}
    ],
    "hattrick": [
        {"teams": "الأهلي ضد الزمالك", "tournament": "الدوري المصري الممتاز"},
        {"teams": "Milan vs Inter", "tournament": "Serie A"},
        {"teams": "PSG vs Marseille", "tournament": "Ligue 1"}
    ]
}

def ask_gemini_matches(channel_key: str):
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"🤖 جاري استخراج مباريات اليوم ({today_str}) لقناة [{channel_key}] عبر Gemini...")

    if not GEMINI_API_KEY or len(GEMINI_API_KEY.strip()) < 10:
        print("⚠️ مفتاح GEMINI_API_KEY غير موجود، سيتم استخدام الجدول المعتمد الافتراضي.")
        return FALLBACK_TARGETS.get(channel_key, [])

    prompt = f"""
    أنت محلل رياضي. اليوم هو {today_str}.
    اذكر فقط المباريات الرسمية أو الودية الحقيقية المنتهية اليوم أو أمس للقناة التالية:
    القناة: '{channel_key}'
    - إذا كانت 'crazy_skills': اختر فقط مباريات المنتخبات الوطنية (دوري الأمم، تصفيات أفريقيا، تصفيات كأس العالم، وديات).
    - إذا كانت '90_plus': اختر كبار أوروبا (إنجلترا، إسبانيا، ألمانيا، دوري الأبطال).
    - إذا كانت 'hattrick': اختر الدوري المصري، أندية أفريقيا، الدوري الإيطالي، الدوري الفرنسي.

    أخرج النتيجة كـ JSON Array فقط بهذا الشكل:
    [
      {{"teams": "البرتغال والنرويج", "tournament": "دوري الأمم الأوروبية"}},
      {{"teams": "المغرب ومالي", "tournament": "تصفيات أمم أفريقيا"}}
    ]
    إذا لم تكن متأكداً، اذكر أبرز مواجهتين من جدول هذا الأسبوع.
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        res = requests.post(url, json=payload, timeout=12)
        if res.status_code == 200:
            text = res.json()['candidates'][0]['content']['parts'][0]['text']
            clean_json = text.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
            matches = json.loads(clean_json)
            if matches:
                return matches
    except Exception as e:
        print(f"⚠️ خطأ أثناء طلب Gemini: {e}")

    return FALLBACK_TARGETS.get(channel_key, [])

def resolve_youtube_url(query: str):
    print(f"🔍 جلب رابط الفيديو لـ: '{query}'...")
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    date_filter = yesterday.strftime("%Y%m%d")

    cmd = [
        "yt-dlp",
        f"ytsearch5:{query}",
        "--dateafter", date_filter,
        "--dump-json",
        "--flat-playlist",
        "--no-warnings"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return None, None

    for line in res.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            item = json.loads(line)
            title = item.get("title", "")
            duration = item.get("duration", 0) or 0
            vid_id = item.get("id")
            
            # استبعاد الألعاب
            t_low = title.lower()
            if any(b in t_low for b in ["fifa", "pes", "efootball", "fc 24", "ps5"]):
                continue

            if 60 <= duration <= 2400:
                return f"https://www.youtube.com/watch?v={vid_id}", title
        except Exception:
            continue

    return None, None

def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else "crazy_skills"
    match_list = ask_gemini_matches(channel)

    queue = []
    for item in match_list:
        teams = item.get("teams", "")
        tournament = item.get("tournament", "")
        search_query = f"ملخص مباراة {teams} {tournament} اليوم"
        url, title = resolve_youtube_url(search_query)
        if url:
            queue.append({
                "url": url,
                "title": title,
                "teams": teams
            })
            print(f"✅ تم تأكيد المباراة: {teams} -> {url}")

    with open("matches_queue.json", "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

    print(f"🎯 الحصيلة النهائية: {len(queue)} مباراة جاهزة للإنتاج.")

if __name__ == "__main__":
    main()

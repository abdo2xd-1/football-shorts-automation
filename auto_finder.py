import os
import sys
import json
import subprocess
import requests
from datetime import datetime, timezone, timedelta

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

BANNED_KEYWORDS = [
    "fifa", "pes", "efootball", "fc 24", "fc 25", "fc 26", "ps5", "ps4",
    "gameplay", "mod", "simulation", "محاكاة", "بلايستيشن", "بيس", "فيفا",
    "women", "female", "liga f", "wsl", "سيدات", "سيدات كرة القدم", "u17", "u19", "u20", "ناشئين"
]

def ask_gemini_matches(channel_key: str):
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"🤖 جاري استشارة Gemini لمباريات اليوم ({today_str}) لقناة [{channel_key}]...")

    channel_rules = {
        "crazy_skills": "مباريات المنتخبات الوطنية الأولى (رجال) فقط مثل دوري الأمم الأوروبية وتصفيات كأس العالم وأفريقيا والوديات الدولية للرجال. ممنوع السيدات وممنوع الأندية.",
        "90_plus": "مباريات كبار أندية الرجال (إنجلترا، إسبانيا، ألمانيا، دوري أبطال أوروبا، كأس العالم للأندية). ممنوع السيدات وممنوع المنتخبات.",
        "hattrick": "مباريات أندية الرجال فقط: الدوري المصري الممتاز، دوري أبطال أفريقيا، الدوري الإيطالي، الدوري الفرنسي. ممنوع السيدات وممنوع المنتخبات."
    }

    prompt = f"""
    أنت محلل وباحث رياضي. تاريخ اليوم: {today_str}.
    اذكر مباريات كرة القدم الرسمية أو الودية للرجال (الفرق الأولى فقط) التي لُعبت اليوم أو انتهت خلال آخر 24 ساعة فقط مطابقة للشروط:
    {channel_rules.get(channel_key, "")}

    ممنوع نهائياً: مباريات السيدات، مباريات الناشئين، أو مباريات قديمة.

    أخرج النتيجة كـ JSON Array نقي فقط بدون أي شرح جانبي:
    [
      {{"team1": "الفريق الأول", "team2": "الفريق الثاني", "tournament": "اسم البطولة"}}
    ]
    إذا لم تكن هناك مباريات منتهية جديدة لهذه الفئة اليوم، أرجع مصفوفة فارغة: []
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code == 200:
            text = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
    except Exception as e:
        print(f"⚠️ تنبيه أثناء طلب Gemini: {e}")

    return []

def resolve_youtube_url(team1: str, team2: str, tournament: str):
    query = f"ملخص مباراة {team1} و {team2} {tournament}"
    print(f"🔍 البحث عن فيديو: {query}")

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
            title_lower = title.lower()

            if any(b in title_lower for b in BANNED_KEYWORDS):
                continue

            if 120 <= duration <= 2100:
                return f"https://www.youtube.com/watch?v={vid_id}", title
        except Exception:
            continue

    return None, None

def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else "crazy_skills"
    matches = ask_gemini_matches(channel)

    queue = []
    for m in matches:
        t1 = m.get("team1")
        t2 = m.get("team2")
        tourn = m.get("tournament", "")
        url, title = resolve_youtube_url(t1, t2, tourn)
        if url:
            queue.append({
                "url": url,
                "title": f"{t1} ضد {t2}",
                "teams": f"{t1} vs {t2}"
            })
            print(f"✅ تم تأكيد المباراة: {t1} ضد {t2}")

    with open("matches_queue.json", "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

    print(f"🎯 الحصيلة النهائية: {len(queue)} مباراة.")

if __name__ == "__main__":
    main()

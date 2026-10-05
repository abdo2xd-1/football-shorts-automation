import os
import sys
import json
import requests
from datetime import datetime, timezone

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TOURNAMENTS_CATALOG = """
1. إنجلترا: الدوري الإنجليزي الممتاز، كأس الاتحاد، كأس الرابطة.
2. إسبانيا: الدوري الإسباني، كأس الملك، السوبر الإسباني.
3. إيطاليا: الدوري الإيطالي، كأس إيطاليا.
4. ألمانيا: الدوري الألماني، كأس ألمانيا.
5. فرنسا: الدوري الفرنسي، كأس فرنسا.
6. مصر: الدوري المصري الممتاز، كأس مصر، السوبر المصري، كأس الرابطة.
7. بطولات الأندية القارية: دوري أبطال أوروبا، الدوري الأوروبي، دوري المؤتمر، دوري أبطال أفريقيا، الكونفيدرالية، كأس العالم للأندية.
8. بطولات المنتخبات الوطنية الأولى (رجال): دوري الأمم الأوروبية، تصفيات كأس العالم، تصفيات أمم أفريقيا، كأس أمم أوروبا، كوبا أمريكا، كأس أمم أفريقيا، كأس آسيا، كأس العالم، والوديات الدولية الرسمية.
"""

def fetch_links_from_gemini(channel_key: str):
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"🤖 جاري استشارة Gemini للبحث في الويب وجلب روابط ملخصات اليوم ({today_str}) لقناة [{channel_key}]...")

    channel_rules = {
        "crazy_skills": "مباريات المنتخبات الوطنية الأولى (رجال) فقط. ممنوع منتخبات السيدات وممنوع أندية الدوريات نهائياً.",
        "90_plus": "مباريات كبار أندية الرجال (إنجلترا، إسبانيا، ألمانيا، دوري أبطال أوروبا، كأس العالم للأندية). ممنوع السيدات وممنوع المنتخبات.",
        "hattrick": "مباريات أندية الرجال فقط: الدوري المصري الممتاز، دوري أبطال أفريقيا، الدوري الإيطالي، والدوري الفرنسي. ممنوع السيدات وممنوع المنتخبات."
    }

    prompt = f"""
    أنت باحث رياضي ذكي ومتصل بالإنترنت.
    التاريخ اليوم هو {today_str}.
    
    القواعد الإلزامية لقناة ({channel_key}):
    {channel_rules.get(channel_key, "")}
    
    البطولات المعتمدة:
    {TOURNAMENTS_CATALOG}

    المهمة:
    1. ابحث على الإنترنت عن المباريات الحقيقية للرجال فقط التي انتهت اليوم أو خلال آخر 24 ساعة فقط.
    2. استخرج رابط يوتيوب الفعلي والمباشر (YouTube URL حقيقي يعمل الآن) لملخص كل مباراة من القنوات الموثوقة (مثل beIN Sports, ON Time Sports, Sky Sports, أو قنوات الاتحادات الرسمية).
    
    ممنوع نهائياً:
    - مباريات السيدات (Women, Liga F, WSL).
    - مباريات قديمة مر عليها أكثر من 24 ساعة.
    - ألعاب البلايستيشن والمحاكاة (FIFA, eFootball, PES, FC 24, FC 25).

    أخرج النتيجة كـ JSON Array نقي فقط بدون أي شرح جانبي:
    [
      {{
        "teams": "اسم الفريقين أو المنتخبين",
        "title": "مباراة كذا ضد كذا",
        "url": "https://www.youtube.com/watch?v=xxxxxxxxxxx"
      }}
    ]
    إذا لم تجد مباريات منتهية جديدة لهذه الفئة اليوم، أرجع مصفوفة فارغة: []
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"googleSearch": {}}]
    }

    try:
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code == 200:
            data = res.json()
            parts = data['candidates'][0]['content']['parts']
            full_text = "".join([p.get('text', '') for p in parts]).strip()

            clean_json = full_text
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            matches = json.loads(clean_json)
            valid = [m for m in matches if "youtube.com/watch" in m.get("url", "") or "youtu.be" in m.get("url", "")]
            print(f"🎯 تم استلام {len(valid)} رابط مباشر من Gemini.")
            return valid
        else:
            print(f"⚠️ خطأ في رد Gemini: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"⚠️ استثناء أثناء استدعاء Gemini: {e}")

    return []

if __name__ == "__main__":
    ch = sys.argv[1] if len(sys.argv) > 1 else "crazy_skills"
    tasks = fetch_links_from_gemini(ch)

    with open("matches_queue.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    print(f"✅ تم حفظ قائمة المهام لقناة [{ch}] في matches_queue.json")

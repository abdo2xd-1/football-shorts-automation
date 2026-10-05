import os
import sys
import json
import requests
from datetime import datetime, timezone

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TOURNAMENTS_CATALOG = """
1. بطولات الدوريات الكبرى والدوري المصري:
- إنجلترا: الدوري الإنجليزي الممتاز (Premier League)، كأس الاتحاد (FA Cup)، كأس الرابطة (Carabao Cup).
- إسبانيا: الدوري الإسباني (La Liga)، كأس الملك (Copa del Rey)، السوبر الإسباني.
- إيطاليا: الدوري الإيطالي (Serie A)، كأس إيطاليا (Coppa Italia).
- ألمانيا: الدوري الألماني (Bundesliga)، كأس ألمانيا (DFB-Pokal).
- فرنسا: الدوري الفرنسي (Ligue 1)، كأس فرنسا (Coupe de France).
- مصر: الدوري المصري الممتاز، كأس مصر، السوبر المصري، كأس الرابطة المصرية.

2. بطولات أندية القارات والعالم:
- دوري أبطال أوروبا، الدوري الأوروبي، دوري المؤتمر، السوبر الأوروبي، كأس العالم للأندية، كأس القارات للأندية.
- دوري أبطال أفريقيا، كأس الكونفيدرالية الأفريقية، السوبر الأفريقي، الدوري الأفريقي (AFL).

3. بطولات المنتخبات الوطنية:
- دوري الأمم الأوروبية (UEFA Nations League)، تصفيات كأس العالم (أوروبا، أفريقيا، آسيا، أمريكا ج، كونكاكاف).
- كأس الأمم الأفريقية (AFCON)، كأس آسيا، كوبا أمريكا، الكأس الذهبية، كأس العالم، الفيناليسيما، والمباريات الودية الدولية الرسمية.
"""

def get_matches_and_urls_from_gemini(channel_key: str):
    """جعل Gemini يبحث على الإنترنت ويجلب روابط ملخصات يوتيوب مباشرة"""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"🤖 جاري استشارة Gemini لجلب المباريات وروابطها لقناة [{channel_key}] ليوم ({today_str})...")

    channel_rules = {
        "crazy_skills": "مباريات المنتخبات الوطنية الرسمية والودية فقط. ممنوع الأندية نهائياً.",
        "90_plus": "كبار أندية أوروبا (إنجلترا، إسبانيا، ألمانيا) ودوري أبطال أوروبا وكأس العالم للأندية. ممنوع المنتخبات.",
        "hattrick": "الدوري المصري، بطولات أفريقيا للأندية، الدوري الإيطالي، والدوري الفرنسي. ممنوع المنتخبات."
    }

    rule = channel_rules.get(channel_key, "")

    prompt = f"""
    أنت باحث رياضي ذكي ومتصل بالإنترنت.
    تاريخ اليوم: {today_str}.
    
    القواعد الصارمة للقناة الحالية ({channel_key}):
    {rule}
    
    القائمة المعتمدة للبطولات:
    {TOURNAMENTS_CATALOG}

    المهمة المطلوبة:
    1. ابحث عن المباريات الحقيقية التي لُعبت اليوم أو انتهت خلال آخر 12 إلى 24 ساعة فقط وتطابق قواعد القناة تماماً.
    2. أحضر رابط يوتيوب المباشر (YouTube URL الحقيقي الصالح) لملخص كل مباراة من القنوات الرسمية أو الموثوقة (مثل beIN Sports, ON Time Sports, Sky Sports, أو ملخصات يوتيوب الرسمية).
    
    تنبيه صارم:
    - ممنوع تماماً ألعاب الفيديو (FIFA, PES, eFootball).
    - يجب أن تكون روابط يوتيوب حقيقية وصالحة تعمل حالياً.

    أخرج النتيجة بصيغة JSON Array نقية فقط دون أي كلام جانبي:
    [
      {{
        "teams": "اسم الفريقين أو المنتخبين",
        "title": "عنوان الملخص",
        "url": "https://www.youtube.com/watch?v=xxxxxxxxxxx"
      }}
    ]
    إذا لم تكن هناك أي مباريات منتهية لهذه الفئة اليوم، أرجع مصفوفة فارغة: []
    """

    # تفعيل ميزة البحث على الويب لـ Gemini (Google Search Tool)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"googleSearch": {}}]
    }

    try:
        res = requests.post(url, json=payload, timeout=25)
        if res.status_code == 200:
            data = res.json()
            parts = data['candidates'][0]['content']['parts']
            full_text = "".join([p.get('text', '') for p in parts])
            
            clean_json = full_text.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            matches = json.loads(clean_json)
            valid_list = [m for m in matches if "youtube.com" in m.get("url", "") or "youtu.be" in m.get("url", "")]
            print(f"🎯 تم استخراج {len(valid_list)} مباراة بروابطها المباشرة من Gemini بنجاح!")
            return valid_list
        else:
            print(f"⚠️ استجابة Gemini فشلت بكود: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء تواصل Gemini: {e}")

    return []

if __name__ == "__main__":
    channel = sys.argv[1] if len(sys.argv) > 1 else "crazy_skills"
    tasks = get_matches_and_urls_from_gemini(channel)

    with open("matches_queue.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    print(f"✅ تم حفظ مهام القناة [{channel}] في matches_queue.json")

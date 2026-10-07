"""Voice alerts in the workforce's languages, pre-generated once as MP3 so the site works offline.

Generation uses Microsoft Edge's online TTS through the `edge-tts` package (internet needed once;
only these fixed phrases are sent). ✍️ The Urdu, Hindi and Bengali phrases need a native-speaker check.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

LANGS = ("ar", "en", "ur", "hi", "bn")
LANG_NAMES = {"ar": "العربية", "en": "English", "ur": "اردو", "hi": "हिन्दी", "bn": "বাংলা"}
VOICES = {
    "ar": "ar-SA-HamedNeural",
    "en": "en-US-GuyNeural",
    "ur": "ur-PK-AsadNeural",
    "hi": "hi-IN-MadhurNeural",
    "bn": "bn-BD-PradeepNeural",
}

PHRASES: dict[str, dict[str, str]] = {
    "zone": {
        "ar": "تنبيه: أنت داخل منطقة خطر. اخرج منها فورًا.",
        "en": "Warning: you are inside a danger zone. Leave it now.",
        "ur": "خبردار! آپ خطرناک علاقے میں ہیں۔ فوراً باہر نکل جائیں۔",
        "hi": "चेतावनी! आप खतरनाक क्षेत्र में हैं। तुरंत बाहर निकलें।",
        "bn": "সতর্কতা! আপনি বিপজ্জনক এলাকায় আছেন। এখনই বেরিয়ে আসুন।",
    },
    "helmet": {
        "ar": "تنبيه: ارتدِ خوذة السلامة.",
        "en": "Please wear your safety helmet.",
        "ur": "براہ کرم حفاظتی ہیلمٹ پہنیں۔",
        "hi": "कृपया सुरक्षा हेलमेट पहनें।",
        "bn": "অনুগ্রহ করে নিরাপত্তা হেলমেট পরুন।",
    },
    "vest": {
        "ar": "تنبيه: ارتدِ السترة العاكسة.",
        "en": "Please wear your high-visibility vest.",
        "ur": "براہ کرم ریفلیکٹو جیکٹ پہنیں۔",
        "hi": "कृपया रिफ्लेक्टिव जैकेट पहनें।",
        "bn": "অনুগ্রহ করে রিফ্লেক্টিভ জ্যাকেট পরুন।",
    },
    "harness": {
        "ar": "تنبيه: ثبّت حزام الأمان قبل العمل على الارتفاع.",
        "en": "Clip on your safety harness before working at height.",
        "ur": "اونچائی پر کام سے پہلے حفاظتی بیلٹ باندھیں۔",
        "hi": "ऊँचाई पर काम करने से पहले सेफ्टी हार्नेस लगाएँ।",
        "bn": "উঁচুতে কাজ করার আগে সেফটি হারনেস পরুন।",
    },
    "emergency": {
        "ar": "حالة طوارئ: عامل يحتاج مساعدة. توجّه إلى موقع التنبيه فورًا.",
        "en": "Emergency: a worker needs help. Go to the alert location now.",
        "ur": "ہنگامی صورتحال: ایک کارکن کو مدد چاہیے۔ فوراً موقع پر پہنچیں۔",
        "hi": "आपातकाल: एक कर्मचारी को मदद चाहिए। तुरंत अलर्ट वाली जगह पहुँचें।",
        "bn": "জরুরি অবস্থা: একজন কর্মীর সাহায্য দরকার। এখনই সতর্কতার স্থানে যান।",
    },
    "machine": {
        "ar": "تنبيه: أنت قريب جدًا من معدة. ابتعد عنها.",
        "en": "Warning: you are too close to a machine. Move away.",
        "ur": "خبردار! آپ مشین کے بہت قریب ہیں۔ دور ہٹ جائیں۔",
        "hi": "चेतावनी! आप मशीन के बहुत पास हैं। दूर हट जाएँ।",
        "bn": "সতর্কতা! আপনি যন্ত্রের খুব কাছে আছেন। দূরে সরে যান।",
    },
    "midday": {
        "ar": "تنبيه: العمل تحت أشعة الشمس ممنوع الآن. انتقل إلى الظل.",
        "en": "Outdoor work in the sun is not allowed now. Move to the shade.",
        "ur": "ابھی دھوپ میں کام منع ہے۔ سائے میں چلے جائیں۔",
        "hi": "अभी धूप में काम करना मना है। छाया में चले जाएँ।",
        "bn": "এখন রোদে কাজ করা নিষেধ। ছায়ায় চলে যান।",
    },
}


def phrase_key(kind: str, item: str | None = None) -> str | None:
    if kind == "zone_intrusion":
        return "zone"
    if kind == "ppe_missing":
        return item if item in PHRASES else None
    if kind in ("man_down", "sos"):
        return "emergency"
    if kind == "midday_exposure":
        return "midday"
    if kind == "machine_proximity":
        return "machine"
    return None


def file_name(key: str, lang: str) -> str:
    return f"{key}_{lang}.mp3"


def manifest(voices_dir: Path) -> dict:
    return {
        "languages": [{"code": c, "name": LANG_NAMES[c]} for c in LANGS],
        "phrases": {
            key: {lang: {"text": text, "url": f"/voices/{file_name(key, lang)}",
                         "available": (voices_dir / file_name(key, lang)).exists()}
                  for lang, text in by_lang.items()}
            for key, by_lang in PHRASES.items()
        },
    }


async def _generate(out_dir: Path, overwrite: bool) -> list[tuple[str, bool, str]]:
    import edge_tts

    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for key, by_lang in PHRASES.items():
        for lang, text in by_lang.items():
            path = out_dir / file_name(key, lang)
            if path.exists() and not overwrite:
                results.append((path.name, True, "exists"))
                continue
            try:
                await edge_tts.Communicate(text, VOICES[lang]).save(str(path))
                results.append((path.name, True, "generated"))
            except Exception as exc:  # noqa: BLE001
                results.append((path.name, False, str(exc)))
    return results


def generate(out_dir: Path, overwrite: bool = False) -> list[tuple[str, bool, str]]:
    return asyncio.run(_generate(out_dir, overwrite))

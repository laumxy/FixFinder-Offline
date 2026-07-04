"""
Localization Engine — offline-first translation and language detection.

Supported languages: en, sw (Swahili), fr (French), ar (Arabic),
                     lg (Luganda), ach (Acholi)

All translations are stored in SQLite (translations table) and fall back
to English when a key is missing. No external APIs are called.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.database.db import get_connection
from fixfinder_engine.config import settings


# ── Built-in string tables ────────────────────────────────────────────────────
# Format: {language_code: {key: value}}
# Keys match the JSON field names returned by the /diagnose endpoint.

_BUILTIN: dict[str, dict[str, str]] = {
    "en": {
        "greeting":           "How can I help you with your repair today?",
        "no_match":           "No matching repair record found for your problem.",
        "safety_warning":     "Safety first: review all warnings before starting work.",
        "follow_up_prompt":   "Please answer the following questions to improve the diagnosis:",
        "confidence_label":   "Confidence",
        "category_label":     "Category",
        "repair_steps_label": "Repair Steps",
        "tools_label":        "Required Tools",
        "safety_label":       "Safety Warnings",
        "prevention_label":   "Prevention",
        "inspection_label":   "Inspection Steps",
        "causes_label":       "Likely Causes",
        "low_confidence_msg": "Confidence is low. More information is needed to give an accurate diagnosis.",
        "unknown_category":   "Problem category could not be determined.",
        "api_error":          "An error occurred. Please try again.",
        "license_required":   "A valid license is required to use this feature.",
        "license_ok":         "License activated successfully.",
        "learn_ok":           "Knowledge base updated successfully.",
    },
    "sw": {
        "greeting":           "Naweza kukusaidia vipi kurekebisha leo?",
        "no_match":           "Hakuna rekodi ya ukarabati inayolingana na tatizo lako.",
        "safety_warning":     "Usalama kwanza: angalia maonyo yote kabla ya kuanza kazi.",
        "follow_up_prompt":   "Tafadhali jibu maswali yafuatayo kuboresha uchunguzi:",
        "confidence_label":   "Uhakika",
        "category_label":     "Aina",
        "repair_steps_label": "Hatua za Ukarabati",
        "tools_label":        "Vifaa Vinavyohitajika",
        "safety_label":       "Maonyo ya Usalama",
        "prevention_label":   "Kuzuia",
        "inspection_label":   "Hatua za Ukaguzi",
        "causes_label":       "Sababu Zinazowezekana",
        "low_confidence_msg": "Uhakika ni mdogo. Taarifa zaidi zinahitajika.",
        "unknown_category":   "Aina ya tatizo haijaweza kuamua.",
        "api_error":          "Hitilafu imetokea. Tafadhali jaribu tena.",
        "license_required":   "Leseni halali inahitajika kutumia kipengele hiki.",
        "license_ok":         "Leseni imeanzishwa kwa mafanikio.",
        "learn_ok":           "Hifadhidata ya maarifa imesasishwa kwa mafanikio.",
    },
    "fr": {
        "greeting":           "Comment puis-je vous aider pour votre réparation aujourd'hui?",
        "no_match":           "Aucun enregistrement de réparation correspondant à votre problème.",
        "safety_warning":     "La sécurité d'abord: consultez tous les avertissements avant de commencer.",
        "follow_up_prompt":   "Veuillez répondre aux questions suivantes pour améliorer le diagnostic:",
        "confidence_label":   "Confiance",
        "category_label":     "Catégorie",
        "repair_steps_label": "Étapes de réparation",
        "tools_label":        "Outils requis",
        "safety_label":       "Avertissements de sécurité",
        "prevention_label":   "Prévention",
        "inspection_label":   "Étapes d'inspection",
        "causes_label":       "Causes probables",
        "low_confidence_msg": "La confiance est faible. Plus d'informations sont nécessaires.",
        "unknown_category":   "La catégorie du problème n'a pas pu être déterminée.",
        "api_error":          "Une erreur s'est produite. Veuillez réessayer.",
        "license_required":   "Une licence valide est requise pour utiliser cette fonctionnalité.",
        "license_ok":         "Licence activée avec succès.",
        "learn_ok":           "Base de connaissances mise à jour avec succès.",
    },
    "ar": {
        "greeting":           "كيف يمكنني مساعدتك في الإصلاح اليوم؟",
        "no_match":           "لم يتم العثور على سجل إصلاح مطابق لمشكلتك.",
        "safety_warning":     "السلامة أولاً: راجع جميع التحذيرات قبل البدء في العمل.",
        "follow_up_prompt":   "يرجى الإجابة على الأسئلة التالية لتحسين التشخيص:",
        "confidence_label":   "الثقة",
        "category_label":     "الفئة",
        "repair_steps_label": "خطوات الإصلاح",
        "tools_label":        "الأدوات المطلوبة",
        "safety_label":       "تحذيرات السلامة",
        "prevention_label":   "الوقاية",
        "inspection_label":   "خطوات الفحص",
        "causes_label":       "الأسباب المحتملة",
        "low_confidence_msg": "الثقة منخفضة. هناك حاجة إلى مزيد من المعلومات.",
        "unknown_category":   "تعذر تحديد فئة المشكلة.",
        "api_error":          "حدث خطأ. يرجى المحاولة مرة أخرى.",
        "license_required":   "مطلوب ترخيص صالح لاستخدام هذه الميزة.",
        "license_ok":         "تم تفعيل الترخيص بنجاح.",
        "learn_ok":           "تم تحديث قاعدة المعرفة بنجاح.",
    },
    "lg": {
        "greeting":           "Nnyinza okukulwanirira atya okuddaabiriza leero?",
        "no_match":           "Tewali record ya okuddaabiriza eyagaana okugoberera ekizibu kyo.",
        "safety_warning":     "Obwekuumi nga bwa mazima: kenggera ebikolwa byonna nga tekitandika.",
        "follow_up_prompt":   "Ndaga okuddamu ebibuuzo ebikyukakyuka okukonkonya okusuzuumula:",
        "confidence_label":   "Ekitiibwa",
        "category_label":     "Ekika",
        "repair_steps_label": "Enteeko z'Okuddaabiriza",
        "tools_label":        "Ebikozesebwa Ebibeera",
        "safety_label":       "Ebikolwa Obwekuumi",
        "prevention_label":   "Okwegalamira",
        "inspection_label":   "Enteeko z'Okusuzuumula",
        "causes_label":       "Ebizibu Ebibeera",
        "low_confidence_msg": "Ekitiibwa kya manyi. Ebikwata ku makulu bingi bibeera.",
        "unknown_category":   "Ekika k'ekizibu tekiyinza kukuuma.",
        "api_error":          "Waliwo ensobi. Geraako nate.",
        "license_required":   "Layisensi ennungi yetaagibwa okukozesa ekikolwa kino.",
        "license_ok":         "Layisensi yatandikibwa bulungi.",
        "learn_ok":           "Ttaka ly'amagezi lysasulibwa bulungi.",
    },
    "ach": {
        "greeting":           "Abinye omiyo konye kwede i twero me cato tin?",
        "no_match":           "Pe tye coc me cato ma rwatte ki ic mamegi.",
        "safety_warning":     "Wellweng yot: nen mot kicika ducu ka pe icako tic.",
        "follow_up_prompt":   "Lagim iye penyo magi me konyo yeo cung:",
        "confidence_label":   "Meno",
        "category_label":     "Lyec",
        "repair_steps_label": "Coc me Cato",
        "tools_label":        "Jami me Tic",
        "safety_label":       "Mot me Wellweng",
        "prevention_label":   "Egamo",
        "inspection_label":   "Coc me Neno",
        "causes_label":       "Tyen ma Rwatte",
        "low_confidence_msg": "Meno nok. Ngec madwong mite.",
        "unknown_category":   "Lyec pa ic pe twero ngene.",
        "api_error":          "Bal otimme. Tem doki.",
        "license_required":   "Layicen ma lonyo mite me tic ki jami man.",
        "license_ok":         "Layicen okwee maleng.",
        "learn_ok":           "Buk pa ngec oketo wa maleng.",
    },
}

# Script patterns for language detection (character ranges)
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_SWAHILI_MARKERS = {
    "nina", "nina", "sijui", "gari", "mvua", "paa", "bomba", "umeme",
    "inashuka", "kuvuja", "imevunjika", "haifanyi", "tatizo", "hawafanyi",
}
_FRENCH_MARKERS = {
    "le", "la", "les", "une", "des", "mon", "ma", "pas", "dans", "sur",
    "pour", "qui", "que", "est", "avec", "il", "elle", "nous", "vous",
}
_LUGANDA_MARKERS = {
    "nga", "nze", "oyo", "eno", "bino", "nnyinza", "tekyali",
    "kizibu", "kino", "ekyo", "ekizibu",
}
_ACHOLI_MARKERS = {
    "tic", "cato", "obedo", "timo", "tye", "magi", "pe", "ngo", "abinye",
}


class LocalizationEngine:
    """Offline-first localization: language detection + string translation."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.database_path
        self._cache: dict[str, dict[str, str]] = {}

    # ── Language detection ────────────────────────────────────────────────────

    def detect_language(self, text: str) -> str:
        """Return a language code based on lightweight heuristics."""
        if not text:
            return settings.default_language

        if _ARABIC_RE.search(text):
            return "ar"

        tokens = set(re.findall(r"[a-zA-Z\u0600-\u06FF]+", text.lower()))

        scores: dict[str, int] = {
            "sw":  len(tokens & _SWAHILI_MARKERS),
            "fr":  len(tokens & _FRENCH_MARKERS),
            "lg":  len(tokens & _LUGANDA_MARKERS),
            "ach": len(tokens & _ACHOLI_MARKERS),
        }
        best = max(scores, key=lambda k: scores[k])
        if scores[best] >= 2:
            return best

        return "en"

    # ── Translation ───────────────────────────────────────────────────────────

    def t(self, key: str, language: str | None = None, fallback: str = "") -> str:
        """Return the translated string for key in the given language."""
        lang = language or settings.default_language
        if lang not in settings.supported_languages:
            lang = "en"

        # 1. In-memory cache
        cached = self._cache.get(lang, {}).get(key)
        if cached:
            return cached

        # 2. DB translations table
        db_value = self._from_db(key, lang)
        if db_value:
            self._cache.setdefault(lang, {})[key] = db_value
            return db_value

        # 3. Built-in table for language
        builtin_lang = _BUILTIN.get(lang, {}).get(key)
        if builtin_lang:
            return builtin_lang

        # 4. English fallback
        en_value = _BUILTIN.get("en", {}).get(key)
        if en_value:
            return en_value

        return fallback or key

    def translate_report(self, report: dict[str, Any], language: str) -> dict[str, Any]:
        """
        Inject localized UI labels into a diagnostic report.
        Does NOT translate the actual repair content (that would require AI).
        Instead it adds a 'labels' block with translated field names so the
        front-end can render them correctly.
        """
        if language == "en":
            return report

        keys = [
            "confidence_label", "category_label", "repair_steps_label",
            "tools_label", "safety_label", "prevention_label",
            "inspection_label", "causes_label",
        ]
        labels = {k: self.t(k, language) for k in keys}
        out = dict(report)
        out["_labels"] = labels
        out["_language"] = language
        if not report.get("final_answer") or "Safety" not in str(report.get("final_answer", "")):
            out["_safety_notice"] = self.t("safety_warning", language)
        return out

    def load_translations_from_db(self, language: str) -> dict[str, str]:
        """Load all translations for a language from the DB into cache."""
        rows = self._db_rows(language)
        result = {r["key"]: r["value"] for r in rows}
        self._cache[language] = result
        return result

    def upsert_translation(self, language: str, key: str, value: str, context: str = "general") -> None:
        """Add or replace a single translation key in the DB."""
        if not self.db_path.exists():
            return
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO translations (language_code, key, value, context)
                VALUES (?,?,?,?)
                ON CONFLICT(language_code, key) DO UPDATE SET value=excluded.value
                """,
                (language, key, value, context),
            )
        # Invalidate cache for this language
        self._cache.pop(language, None)

    def bulk_upsert(self, language: str, translations: dict[str, str]) -> int:
        """Upsert a dictionary of {key: value} pairs for a language."""
        if not self.db_path.exists():
            return 0
        with get_connection(self.db_path) as conn:
            for key, value in translations.items():
                conn.execute(
                    """
                    INSERT INTO translations (language_code, key, value)
                    VALUES (?,?,?)
                    ON CONFLICT(language_code, key) DO UPDATE SET value=excluded.value
                    """,
                    (language, key, value),
                )
        self._cache.pop(language, None)
        return len(translations)

    def supported(self) -> list[dict[str, str]]:
        names = {
            "en": "English", "sw": "Swahili", "fr": "French",
            "ar": "Arabic", "lg": "Luganda", "ach": "Acholi",
        }
        return [
            {"code": code, "name": names.get(code, code)}
            for code in settings.supported_languages
        ]

    # ── Private ───────────────────────────────────────────────────────────────

    def _from_db(self, key: str, language: str) -> str | None:
        if not self.db_path.exists():
            return None
        rows = self._db_rows(language, key=key)
        return rows[0]["value"] if rows else None

    def _db_rows(self, language: str, key: str | None = None) -> list:
        if not self.db_path.exists():
            return []
        try:
            with get_connection(self.db_path) as conn:
                if key:
                    rows = conn.execute(
                        "SELECT key, value FROM translations WHERE language_code=? AND key=?",
                        (language, key),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT key, value FROM translations WHERE language_code=?",
                        (language,),
                    ).fetchall()
            return [{"key": r["key"], "value": r["value"]} for r in rows]
        except Exception:
            return []


# Module-level singleton
localizer = LocalizationEngine()

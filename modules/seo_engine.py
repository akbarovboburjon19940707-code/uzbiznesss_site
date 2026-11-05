"""
BizplanAI — SEO Engine (Sitemap, Slugs, Schema.org, Structured Data)
=====================================================================
Google qidiruvida 1-o'ringa chiqish uchun barcha mahsulotlarni
indekslash, sluglar yaratish va sitemap.xml generatsiyasi.
"""
import os
import re
import logging
from datetime import datetime
from database import db
from models.business import BusinessPlan

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """O'zbekcha matnni URL-friendly (faqat ASCII a-z0-9) slug formatiga o'tkazish."""
    if not text:
        return "biznes-reja"
    text = text.lower().strip()
    replacements = {
        "o'": "o", "g'": "g", "sh": "sh", "ch": "ch", "oʻ": "o", "gʻ": "g",
        "o‘": "o", "g‘": "g", "o`": "o", "g`": "g",
        "’": "", "'": "", "ʻ": "", "`": "", "\"": "", "«": "", "»": "",
        "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "",
        "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "%": "foiz", "+": "va"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    text = re.sub(r"-+", "-", text)
    return text[:90].strip("-") or "biznes-reja"


def generate_meta_description(plan: BusinessPlan) -> str:
    """Google snippet uchun optimallashtirilgan meta tavsif."""
    title = plan.title or "Biznes reja"
    category = plan.category or "Tadbirkorlik"
    price = f"{int(plan.price):,} so'm".replace(",", " ") if plan.price else "25 000 so'm"
    pages = f"{plan.total_pages} betlik" if plan.total_pages and plan.total_pages > 0 else "to'liq"

    desc = f"{title} — {category} yo'nalishi bo'yicha {pages} professional tayyor biznes reja namunasi. " \
           f"Kredit olish va investitsiya jalb qilish uchun hisob-kitoblar. Narxi: {price}. Format: PDF / Word."
    return desc[:280]


def sync_all_slugs():
    """
    Barcha biznes rejalar uchun unikal SEO slug va meta description yaratish.
    PostgreSQL unique index to'qnashuvini oldini olish uchun avval o'zgaradigan
    sluglarni NULL qilib flush qiladi, so'ng yangi qiymatlarni yozadi.
    """
    try:
        plans = BusinessPlan.query.order_by(BusinessPlan.id.asc()).all()
        used_slugs = set()
        desired_slugs = {}
        slug_changes = []
        meta_changes = 0

        for p in plans:
            base_slug = slugify(p.title)
            slug = base_slug
            counter = 1
            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1
            used_slugs.add(slug)
            desired_slugs[p.id] = slug

            if p.slug != slug:
                slug_changes.append(p)

            if not p.meta_description:
                p.meta_description = generate_meta_description(p)
                meta_changes += 1

        if slug_changes:
            # PostgreSQL unique constraint to'qnashuvini oldini olish uchun
            # o'zgarayotgan qatorlarning slug ustunini vaqtincha None qilamiz
            for p in slug_changes:
                p.slug = None
            db.session.flush()

            for p in slug_changes:
                p.slug = desired_slugs[p.id]

        total_updated = len(slug_changes) + meta_changes
        if total_updated > 0:
            db.session.commit()
            logger.info(f"[SEO] {len(slug_changes)} ta slug va {meta_changes} ta meta tavsif yangilandi.")
        return total_updated
    except Exception as e:
        db.session.rollback()
        logger.error(f"[SEO] sync_all_slugs xatolik: {e}", exc_info=True)
        return 0


def get_plan_by_slug_or_id(slug_or_id: str):
    """Rejani slug yoki ID bo'yicha topish."""
    if not slug_or_id:
        return None
    # 1. Slug bo'yicha
    plan = BusinessPlan.query.filter_by(slug=slug_or_id, is_active=True).first()
    if plan:
        return plan
    # 2. ID bo'yicha
    plan = BusinessPlan.query.filter_by(id=slug_or_id, is_active=True).first()
    return plan


def get_related_plans(plan: BusinessPlan, limit: int = 4):
    """Shu kategoriyadagi boshqa rejalarni qaytarish (ichki SEO linking)."""
    try:
        return BusinessPlan.query.filter(
            BusinessPlan.category == plan.category,
            BusinessPlan.id != plan.id,
            BusinessPlan.is_active == True
        ).order_by(BusinessPlan.created_at.desc()).limit(limit).all()
    except Exception:
        return []
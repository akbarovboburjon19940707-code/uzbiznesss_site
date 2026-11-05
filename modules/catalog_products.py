"""
Tayyor Biznes Rejalar — Mahsulotlar Katalogi (SQL + R2 Edition)
================================================================
SQL bazada (BusinessPlan modeli) saqlanadigan mahsulotlar katalogi.
Fayllar: Cloudflare R2 (bulut) + lokal fallback.

MUHIM: Barcha funksiya nomlari va qaytariladigan formatlar avvalgidek.
       app.py dagi import lar va API endpoint lar o'zgarishsiz ishlaydi.
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional, List

from database import db
from models.business import BusinessPlan

logger = logging.getLogger(__name__)

# ── Paths (lokal fallback uchun) ──────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
CATALOG_DIR = os.path.join(DATA_DIR, "payments_data", "catalog_files")
CATALOG_JSON_FILE = os.path.join(DATA_DIR, "payments_data", "catalog_products.json")

# Papkalarni yaratish
os.makedirs(CATALOG_DIR, exist_ok=True)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════
# INIT — Flask app kontekstida chaqiriladi (app.py dan)
# ══════════════════════════════════════════════════════════════

def init_catalog(app):
    """
    Katalogni ishga tushirish:
    1. business_plans jadvalini yaratish (agar yo'q bo'lsa)
    2. JSON dan SQL ga bir martalik migratsiya
    3. Default mahsulotlarni yaratish (agar baza bo'sh bo'lsa)
    """
    with app.app_context():
        # Jadval yaratish (SQLite dev uchun, production da migrate ishlatiladi)
        db.create_all()

        # JSON → SQL migratsiya
        _migrate_json_to_sql()

        # Default mahsulotlar
        _initialize_default_products()

    logger.info("[CATALOG] Katalog SQL bazasi tayyor")


def _migrate_json_to_sql():
    """JSON dagi mahsulotlarni SQL ga ko'chirish (bir martalik)."""
    if not os.path.exists(CATALOG_JSON_FILE):
        return

    try:
        with open(CATALOG_JSON_FILE, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        if not isinstance(catalog, dict) or not catalog:
            return

        migrated = 0
        for product_id, data in catalog.items():
            # Agar allaqachon SQL da bo'lsa, o'tkazib yuborish
            existing = db.session.get(BusinessPlan, product_id)
            if existing:
                continue

            # File hajmini hisoblash
            file_size = None
            pdf_file = data.get("pdf_file", "")
            if pdf_file:
                pdf_path = os.path.join(CATALOG_DIR, pdf_file)
                if os.path.exists(pdf_path):
                    file_size = os.path.getsize(pdf_path)

            bp = BusinessPlan(
                id=product_id,
                title=data.get("title", "Nomsiz"),
                category=data.get("category", "Umumiy"),
                description=data.get("description", ""),
                price=data.get("price", 30000),
                preview_image=data.get("preview_image", ""),
                pdf_file=pdf_file,
                file_size_bytes=file_size,
                total_pages=data.get("total_pages", 0),
                is_active=data.get("is_active", True),
                download_count=data.get("download_count", 0),
                view_count=0,
            )
            db.session.add(bp)
            migrated += 1

        if migrated > 0:
            db.session.commit()
            logger.info(f"[CATALOG] ✅ JSON dan SQL ga {migrated} mahsulot ko'chirildi")

            # JSON faylni backup qilish (o'chirilmaydi, faqat nomlanadi)
            backup = CATALOG_JSON_FILE + ".migrated_backup"
            if not os.path.exists(backup):
                os.rename(CATALOG_JSON_FILE, backup)
                logger.info(f"[CATALOG] JSON fayl backup: {backup}")

            # Lokal PDF fayllarni R2 ga yuklash (agar R2 mavjud bo'lsa)
            try:
                from modules.r2_storage import is_r2_available, upload_from_path, r2_pdf_key
                if is_r2_available():
                    for product_id, data in catalog.items():
                        pdf_name = data.get("pdf_file", "")
                        if pdf_name:
                            local_pdf = os.path.join(CATALOG_DIR, pdf_name)
                            if os.path.exists(local_pdf):
                                upload_from_path(local_pdf, r2_pdf_key(pdf_name))
                    logger.info("[CATALOG] Lokal PDF lar R2 ga yuklandi")
            except Exception as e:
                logger.warning(f"[CATALOG] R2 ga yuklashda xatolik (davom etamiz): {e}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"[CATALOG] JSON → SQL migratsiya xatolik: {e}")


def _initialize_default_products():
    """Boshlang'ich mahsulotlarni yaratish (agar bo'sh bo'lsa)."""
    # HOWO PDF ni xavfsiz papkaga ko'chirish
    howo_source = os.path.join(BASE_DIR, "static", "uploads",
                               "HOWO avtomobil sotib olish biznes rejasi.pdf")
    howo_pdf_name = "HOWO_avtomobil_sotib_olish_biznes_rejasi.pdf"
    howo_dest = os.path.join(CATALOG_DIR, howo_pdf_name)

    if os.path.exists(howo_source) and not os.path.exists(howo_dest):
        try:
            import shutil
            shutil.copy2(howo_source, howo_dest)
            logger.info(f"[CATALOG] HOWO PDF ko'chirildi: {howo_dest}")
        except Exception as e:
            logger.error(f"[CATALOG] HOWO PDF ko'chirishda xatolik: {e}")

    # SQL da mahsulot borligini tekshirish
    count = BusinessPlan.query.count()
    if count > 0:
        return  # Baza bo'sh emas — default kerak emas

    file_size = None
    if os.path.exists(howo_dest):
        file_size = os.path.getsize(howo_dest)

    howo = BusinessPlan(
        id="howo-transport-lizing",
        title="HOWO avtomobil sotib olish biznes rejasi",
        category="Transport / Lizing",
        description="HOWO yuk avtomobili sotib olish va transport xizmati ko'rsatish "
                    "bo'yicha to'liq professional biznes reja. Moliyaviy hisob-kitoblar, "
                    "kredit grafigi, NPV va ROI tahlili kiritilgan.",
        price=30000,
        preview_image="/static/img/catalog-howo.png",
        pdf_file=howo_pdf_name,
        file_size_bytes=file_size,
        total_pages=0,
        is_active=True,
        download_count=0,
    )
    db.session.add(howo)
    db.session.commit()
    logger.info("[CATALOG] Default mahsulotlar yaratildi (SQL)")


# ══════════════════════════════════════════════════════════════
# PUBLIC API — funksiya nomlari va formatlar avvalgidek
# ══════════════════════════════════════════════════════════════

def get_all_products(active_only: bool = True, include_file_info: bool = False) -> List[dict]:
    """
    Barcha mahsulotlarni olish (frontend uchun xavfsiz format).

    Args:
        active_only: Faqat faol mahsulotlar
        include_file_info: True bo'lsa pdf_file, total_pages, created_at ham qaytaradi (admin uchun)
    """
    query = BusinessPlan.query
    if active_only:
        query = query.filter_by(is_active=True)

    query = query.order_by(BusinessPlan.created_at.desc())
    all_products = query.all()

    products = []
    for bp in all_products:
        # File hajmini formatlash
        file_size_formatted = "3.44 MB"
        if bp.file_size_bytes:
            if bp.file_size_bytes < 1024 * 1024:
                file_size_formatted = f"{bp.file_size_bytes / 1024:.2f} KB"
            else:
                file_size_formatted = f"{bp.file_size_bytes / (1024 * 1024):.2f} MB"
        else:
            # Lokal fayldan hajmini hisoblash (fallback)
            local_path = _get_local_pdf_path(bp)
            if local_path and os.path.exists(local_path):
                size = os.path.getsize(local_path)
                if size < 1024 * 1024:
                    file_size_formatted = f"{size / 1024:.2f} KB"
                else:
                    file_size_formatted = f"{size / (1024 * 1024):.2f} MB"

        # File extension
        file_extension = ".pdf"
        if bp.pdf_file and "." in bp.pdf_file:
            file_extension = "." + bp.pdf_file.rsplit(".", 1)[-1].lower()

        price = int(bp.price) if bp.price else 30000

        item = {
            "id": bp.id,
            "title": bp.title,
            "category": bp.category or "Fayllar",
            "description": bp.description or "",
            "price": price,
            "price_formatted": f"{price:,}".replace(",", " ") + " so'm",
            "preview_image": bp.preview_image or "",
            "download_count": bp.download_count or 0,
            "is_active": bp.is_active,
            "file_extension": file_extension,
            "file_size_formatted": file_size_formatted,
            "views_count": bp.view_count or 0,
        }

        # Admin uchun qo'shimcha ma'lumotlar
        if include_file_info:
            item["pdf_file"] = bp.pdf_file or ""
            item["total_pages"] = bp.total_pages or 0
            item["created_at"] = bp.created_at.strftime("%Y-%m-%d %H:%M:%S") if bp.created_at else ""

        products.append(item)

    return products


def get_product_by_id(product_id: str) -> Optional[dict]:
    """Bitta mahsulotni ID bo'yicha olish (ichki ishlatish uchun — pdf_file ham qaytaradi)."""
    bp = db.session.get(BusinessPlan, product_id)
    if not bp:
        return None

    price = int(bp.price) if bp.price else 30000

    return {
        "id": bp.id,
        "title": bp.title,
        "category": bp.category or "Umumiy",
        "description": bp.description or "",
        "price": price,
        "preview_image": bp.preview_image or "",
        "pdf_file": bp.pdf_file or "",
        "total_pages": bp.total_pages or 0,
        "is_active": bp.is_active,
        "download_count": bp.download_count or 0,
        "created_at": bp.created_at.strftime("%Y-%m-%d %H:%M:%S") if bp.created_at else _now(),
        "updated_at": bp.updated_at.strftime("%Y-%m-%d %H:%M:%S") if bp.updated_at else _now(),
    }


def get_product_pdf_path(product_id: str) -> Optional[str]:
    """
    Mahsulotning PDF fayl yo'lini qaytarish.
    Avval lokal tekshiradi, topilmasa R2 dan yuklab oladi.
    """
    bp = db.session.get(BusinessPlan, product_id)
    if not bp or not bp.pdf_file:
        return None

    # 1. Lokal faylni tekshirish
    local_path = _get_local_pdf_path(bp)
    if local_path and os.path.exists(local_path):
        return local_path

    # 2. R2 dan yuklab olish (agar mavjud bo'lsa)
    try:
        from modules.r2_storage import is_r2_available, download_to_path, r2_pdf_key
        if is_r2_available():
            dest_path = os.path.join(CATALOG_DIR, bp.pdf_file)
            key = r2_pdf_key(bp.pdf_file)
            if download_to_path(key, dest_path):
                logger.info(f"[CATALOG] PDF R2 dan yuklandi: {bp.pdf_file}")
                return dest_path
    except Exception as e:
        logger.warning(f"[CATALOG] R2 dan yuklashda xatolik: {e}")

    return None


def _get_local_pdf_path(bp) -> Optional[str]:
    """Lokal PDF fayl yo'lini topish (kategoriya papkasi va asosiy papkadan izlaydi)."""
    pdf_file = bp.pdf_file if isinstance(bp, BusinessPlan) else bp.get("pdf_file", "")
    if not pdf_file:
        return None

    category = bp.category if isinstance(bp, BusinessPlan) else bp.get("category", "")
    folder = CATEGORY_MAP.get(category, "")

    # 1. Kategoriya papkasi: catalog_files/<folder>/<pdf_file>
    if folder:
        cat_path = os.path.join(CATALOG_DIR, folder, pdf_file)
        if os.path.exists(cat_path):
            return cat_path

    # 2. Barcha kategoriya papkalarini tekshirish
    for subfolder in ("xizmatlar", "ishlab_chiqarish", "transport", "lizing", "qishloq_xojaligi", "savdo", "talim", "umumiy"):
        sub_path = os.path.join(CATALOG_DIR, subfolder, pdf_file)
        if os.path.exists(sub_path):
            return sub_path

    # 3. Asosiy joy: catalog_files/
    pdf_path = os.path.join(CATALOG_DIR, pdf_file)
    if os.path.exists(pdf_path):
        return pdf_path

    # 4. Fallback: static/uploads/
    fallback = os.path.join(BASE_DIR, "static", "uploads", pdf_file)
    if os.path.exists(fallback):
        return fallback

    # 5. Probellar bilan: HOWO_... → HOWO ...
    original_name = pdf_file.replace("_", " ")
    fallback2 = os.path.join(BASE_DIR, "static", "uploads", original_name)
    if os.path.exists(fallback2):
        return fallback2

    return None


def increment_download_count(product_id: str):
    """Yuklab olish hisoblagichini oshirish."""
    bp = db.session.get(BusinessPlan, product_id)
    if bp:
        bp.download_count = (bp.download_count or 0) + 1
        db.session.commit()


def add_product(data: dict) -> dict:
    """Yangi mahsulot qo'shish (admin)."""
    import uuid

    product_id = data.get("id") or str(uuid.uuid4())[:12]

    # Fayl hajmini hisoblash
    file_size = None
    pdf_file = data.get("pdf_file", "")
    if pdf_file:
        local_pdf = os.path.join(CATALOG_DIR, pdf_file)
        if os.path.exists(local_pdf):
            file_size = os.path.getsize(local_pdf)

        # R2 ga yuklash
        try:
            from modules.r2_storage import is_r2_available, upload_from_path, r2_pdf_key
            if is_r2_available() and os.path.exists(local_pdf):
                upload_from_path(local_pdf, r2_pdf_key(pdf_file))
        except Exception as e:
            logger.warning(f"[CATALOG] R2 ga PDF yuklashda xatolik: {e}")

    # Preview rasmni R2 ga yuklash
    preview_image = data.get("preview_image", "")
    if preview_image and preview_image.startswith("/static/img/"):
        try:
            from modules.r2_storage import is_r2_available, upload_from_path, r2_image_key, get_public_url
            if is_r2_available():
                img_filename = preview_image.split("/")[-1]
                local_img = os.path.join(BASE_DIR, "static", "img", img_filename)
                if os.path.exists(local_img):
                    key = r2_image_key(img_filename)
                    upload_from_path(local_img, key)
                    # R2 public URL mavjud bo'lsa, shuni ishlatamiz
                    r2_url = get_public_url(key)
                    if r2_url:
                        preview_image = r2_url
        except Exception as e:
            logger.warning(f"[CATALOG] R2 ga rasm yuklashda xatolik: {e}")

    price = int(data.get("price", 30000))

    bp = BusinessPlan(
        id=product_id,
        title=data.get("title", "Nomsiz mahsulot"),
        category=data.get("category", "Umumiy"),
        description=data.get("description", ""),
        price=price,
        preview_image=preview_image,
        pdf_file=pdf_file,
        file_size_bytes=file_size,
        total_pages=int(data.get("total_pages", 0)),
        is_active=data.get("is_active", True),
        download_count=0,
    )
    db.session.add(bp)
    db.session.commit()

    logger.info(f"[CATALOG] Yangi mahsulot: {product_id} — {bp.title}")

    return {
        "id": bp.id,
        "title": bp.title,
        "category": bp.category,
        "description": bp.description,
        "price": price,
        "preview_image": bp.preview_image or "",
        "pdf_file": bp.pdf_file or "",
        "total_pages": bp.total_pages or 0,
        "is_active": bp.is_active,
        "download_count": 0,
        "created_at": bp.created_at.strftime("%Y-%m-%d %H:%M:%S") if bp.created_at else _now(),
        "updated_at": bp.updated_at.strftime("%Y-%m-%d %H:%M:%S") if bp.updated_at else _now(),
    }


def update_product(product_id: str, data: dict) -> Optional[dict]:
    """Mahsulotni tahrirlash."""
    bp = db.session.get(BusinessPlan, product_id)
    if not bp:
        return None

    # Yangilanadigan maydonlar
    field_map = {
        "title": "title",
        "category": "category",
        "description": "description",
        "price": "price",
        "preview_image": "preview_image",
        "pdf_file": "pdf_file",
        "total_pages": "total_pages",
        "is_active": "is_active",
    }

    for data_key, model_key in field_map.items():
        if data_key in data:
            setattr(bp, model_key, data[data_key])

    # Yangi PDF yuklangan bo'lsa, hajmini yangilash + R2 ga yuklash
    if "pdf_file" in data and data["pdf_file"]:
        local_pdf = os.path.join(CATALOG_DIR, data["pdf_file"])
        if os.path.exists(local_pdf):
            bp.file_size_bytes = os.path.getsize(local_pdf)
            try:
                from modules.r2_storage import is_r2_available, upload_from_path, r2_pdf_key
                if is_r2_available():
                    upload_from_path(local_pdf, r2_pdf_key(data["pdf_file"]))
            except Exception as e:
                logger.warning(f"[CATALOG] R2 yangilashda xatolik: {e}")

    db.session.commit()

    price = int(bp.price) if bp.price else 30000
    return {
        "id": bp.id,
        "title": bp.title,
        "category": bp.category,
        "description": bp.description or "",
        "price": price,
        "preview_image": bp.preview_image or "",
        "pdf_file": bp.pdf_file or "",
        "total_pages": bp.total_pages or 0,
        "is_active": bp.is_active,
        "download_count": bp.download_count or 0,
        "created_at": bp.created_at.strftime("%Y-%m-%d %H:%M:%S") if bp.created_at else _now(),
        "updated_at": bp.updated_at.strftime("%Y-%m-%d %H:%M:%S") if bp.updated_at else _now(),
    }


def delete_product(product_id: str) -> bool:
    """Mahsulotni o'chirish (SQL + R2 dan)."""
    bp = db.session.get(BusinessPlan, product_id)
    if not bp:
        return False

    # R2 dan faylni o'chirish
    if bp.pdf_file:
        try:
            from modules.r2_storage import is_r2_available, delete_file, r2_pdf_key
            if is_r2_available():
                delete_file(r2_pdf_key(bp.pdf_file))
        except Exception as e:
            logger.warning(f"[CATALOG] R2 dan o'chirishda xatolik: {e}")

    db.session.delete(bp)
    db.session.commit()
    logger.info(f"[CATALOG] Mahsulot o'chirildi: {product_id}")
    return True



# ══════════════════════════════════════════════════════════════
# KATEGORIYA BO'YICHA FILTR + LAZY LOADING API
# ══════════════════════════════════════════════════════════════

# Kategoriya guruhlash xaritasi (DB dagi qiymatlar → papka nomi)
CATEGORY_MAP = {
    "Xizmatlar":         "xizmatlar",
    "Ishlab chiqarish":  "ishlab_chiqarish",
    "Transport / Lizing": "transport",
    "Lizing":            "lizing",
    "Qishloq xo'jaligi": "qishloq_xojaligi",
    "Savdo":             "savdo",
    "Ta'lim":            "talim",
    "Umumiy":            "umumiy",
}

# Teskari xarita: papka nomi → DB category qiymati (bir papka → bir necha category)
FOLDER_TO_CATEGORIES = {
    "xizmatlar":        ["Xizmatlar"],
    "ishlab_chiqarish": ["Ishlab chiqarish"],
    "transport":        ["Transport / Lizing", "Lizing"],
    "lizing":           ["Transport / Lizing", "Lizing"],
    "qishloq_xojaligi": ["Qishloq xo'jaligi"],
    "savdo":            ["Savdo"],
    "talim":            ["Ta'lim"],
    "umumiy":           ["Umumiy"],
}

# Frontend uchun bo'limlar ro'yxati (tartibda)
CATALOG_SECTIONS = [
    {"key": "xizmatlar",        "label": "Xizmatlar",        "icon": "🏢"},
    {"key": "ishlab_chiqarish", "label": "Ishlab chiqarish", "icon": "🏭"},
    {"key": "transport",        "label": "Transport",        "icon": "🚛"},
    {"key": "lizing",           "label": "Lizing",           "icon": "🔑"},
    {"key": "qishloq_xojaligi", "label": "Qishloq xo'jaligi","icon": "🌾"},
    {"key": "savdo",            "label": "Savdo",            "icon": "🛒"},
    {"key": "talim",            "label": "Ta'lim",           "icon": "🎓"},
    {"key": "umumiy",           "label": "Umumiy",           "icon": "📋"},
]


def get_catalog_categories() -> List[dict]:
    """
    Mavjud kategoriyalar ro'yxatini (soni bilan) qaytarish.
    Faqat kamida 1 ta faol mahsulot bo'lgan bo'limlar qaytariladi.
    """
    try:
        from sqlalchemy import func
        rows = (
            db.session.query(BusinessPlan.category, func.count(BusinessPlan.id))
            .filter(BusinessPlan.is_active == True)
            .group_by(BusinessPlan.category)
            .all()
        )

        # Papka bo'yicha jamlash
        folder_counts = {}
        for db_cat, cnt in rows:
            folder_key = CATEGORY_MAP.get(db_cat, "umumiy")
            folder_counts[folder_key] = folder_counts.get(folder_key, 0) + cnt

        # CATALOG_SECTIONS tartibida, faqat mavjud bo'limlari
        result = []
        for section in CATALOG_SECTIONS:
            key = section["key"]
            if folder_counts.get(key, 0) > 0:
                result.append({
                    "key":   key,
                    "label": section["label"],
                    "icon":  section["icon"],
                    "count": folder_counts[key],
                })
        return result
    except Exception as e:
        logger.error(f"[CATALOG] get_catalog_categories xatolik: {e}")
        return []


def get_products_by_category(
    folder_key: str,
    page: int = 1,
    per_page: int = 20
) -> dict:
    """
    Papka bo'yicha mahsulotlarni sahifalab qaytarish (lazy loading).

    Args:
        folder_key:  'xizmatlar', 'ishlab_chiqarish', 'transport', ...
        page:        Sahifa raqami (1 dan boshlanadi)
        per_page:    Bir sahifadagi mahsulot soni (max 50)

    Returns:
        {
            "products": [...],
            "page": 1,
            "per_page": 20,
            "total": 88,
            "has_more": True
        }
    """
    per_page = min(int(per_page), 50)
    page     = max(int(page), 1)
    offset   = (page - 1) * per_page

    # Papkaga tegishli DB category qiymatlari
    db_categories = FOLDER_TO_CATEGORIES.get(folder_key)
    if not db_categories:
        # Noma'lum papka — bo'sh natija
        return {"products": [], "page": page, "per_page": per_page, "total": 0, "has_more": False}

    try:
        base_q = BusinessPlan.query.filter(
            BusinessPlan.is_active == True,
            BusinessPlan.category.in_(db_categories)
        )
        total = base_q.count()
        bps   = base_q.order_by(BusinessPlan.created_at.desc()).offset(offset).limit(per_page).all()

        products = []
        for bp in bps:
            # File hajmini formatlash
            file_size_formatted = "3.44 MB"
            if bp.file_size_bytes:
                if bp.file_size_bytes < 1024 * 1024:
                    file_size_formatted = f"{bp.file_size_bytes / 1024:.2f} KB"
                else:
                    file_size_formatted = f"{bp.file_size_bytes / (1024 * 1024):.2f} MB"

            price = int(bp.price) if bp.price else 30000
            products.append({
                "id":                 bp.id,
                "title":              bp.title,
                "category":           bp.category or "Fayllar",
                "description":        bp.description or "",
                "price":              price,
                "price_formatted":    f"{price:,}".replace(",", " ") + " so'm",
                "preview_image":      bp.preview_image or "",
                "download_count":     bp.download_count or 0,
                "file_extension":     ".pdf",
                "file_size_formatted": file_size_formatted,
                "views_count":        bp.view_count or 0,
            })

        return {
            "products": products,
            "page":     page,
            "per_page": per_page,
            "total":    total,
            "has_more": (offset + len(bps)) < total,
        }

    except Exception as e:
        logger.error(f"[CATALOG] get_products_by_category xatolik: {e}")
        return {"products": [], "page": page, "per_page": per_page, "total": 0, "has_more": False}


def get_preview_page_numbers(total_pages: int, count: int = 6) -> List[int]:
    """
    PDF dan preview sahifa raqamlarini hisoblash.
    Boshi, o'rtasi, oxiridan 5-6 sahifa tanlaydi.

    Masalan 30 sahifa uchun: [1, 2, 10, 15, 25, 30]
    """
    if total_pages <= 0:
        return [1]

    if total_pages <= count:
        return list(range(1, total_pages + 1))

    pages = set()

    # Boshidan 2 sahifa
    pages.add(1)
    pages.add(2)

    # O'rtadan 2 sahifa
    mid = total_pages // 2
    pages.add(mid)
    pages.add(mid + 1)

    # Oxiridan 2 sahifa
    pages.add(total_pages - 1)
    pages.add(total_pages)

    # Sortlash va kerakli miqdorga kamaytirish
    result = sorted(pages)
    return result[:count]

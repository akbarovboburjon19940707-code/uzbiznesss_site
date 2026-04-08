"""
Input Validatsiya Moduli
========================
"""

def safe_float(value, default=0.0):
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    try:
        return int(float(value)) if value else default
    except (ValueError, TypeError):
        return default

def validate_form(form_data: dict) -> list:
    """Form ma'lumotlarini server-side tekshirish."""
    errors = []

    required = {"loyiha_nomi": "Loyiha nomi", "tashabbuskor": "Tashabbuskor"}
    for field, name in required.items():
        if not form_data.get(field, "").strip():
            errors.append(f"{name} kiritilishi shart")

    number_fields = {
        "loyiha_qiymati": ("Loyiha qiymati", 0, 1e15),
        "oz_mablag": ("O'z mablag'i", 0, 1e15),
        "kredit": ("Kredit summasi", 0, 1e15),
        "muddat": ("Kredit muddati (oy)", 1, 600),
        "foiz": ("Foiz stavkasi", 0, 100),
        "imtiyoz": ("Imtiyozli davr", 0, 600),
    }

    for field, (name, min_v, max_v) in number_fields.items():
        val = form_data.get(field, "")
        if val:
            try:
                num = float(val)
                if num < min_v:
                    errors.append(f"{name} {min_v} dan kam bo'lishi mumkin emas")
                if num > max_v:
                    errors.append(f"{name} {max_v} dan oshmasligi kerak")
            except (ValueError, TypeError):
                errors.append(f"{name} son bo'lishi kerak")

    # Kredit <= loyiha qiymati
    try:
        kredit = float(form_data.get("kredit", 0) or 0)
        qiymat = float(form_data.get("loyiha_qiymati", 0) or 0)
        if kredit > qiymat > 0:
            errors.append("Kredit loyiha qiymatidan oshmasligi kerak")
    except (ValueError, TypeError):
        pass

    # Imtiyoz <= muddat
    try:
        imtiyoz = int(float(form_data.get("imtiyoz", 0) or 0))
        muddat = int(float(form_data.get("muddat", 0) or 0))
        if imtiyoz >= muddat > 0:
            errors.append("Imtiyozli davr kredit muddatidan kam bo'lishi kerak")
    except (ValueError, TypeError):
        pass

    return errors

"""
Document Engine — Word yaratish va PDF konvertatsiya
"""
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from pypdf import PdfReader, PdfWriter
import shutil
import os
import logging
import docx

logger = logging.getLogger(__name__)


def create_word_document(template_path: str, output_path: str, context: dict = None, 
                         images: dict = None, model = None) -> str:
    """Ma'lumotlarni to'g'ridan-to'g'ri Word shablonga yozish."""
    shutil.copy2(template_path, output_path)

    doc = Document(output_path)

    # 1. Placeholder replacement
    data = {}
    if context:
        for k, v in context.items():
            key = "{{" + k + "}}"
            if v is not None and isinstance(v, (int, float)):
                if k in ['foiz', 'irr', 'roi', 'muddat', 'imtiyoz', 'payback', 'pi']:
                    val = str(v)
                else:
                    val = f"{v:,.0f}".replace(",", " ")
            else:
                val = "" if v is None else str(v)
            data[key] = val

    for p in doc.paragraphs:
        _replace_in_paragraph(p, data, images)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _replace_in_paragraph(p, data, images)

    # Header/Footer
    for section in doc.sections:
        for head_foot in [section.header, section.footer]:
            if head_foot:
                for p in head_foot.paragraphs:
                    _replace_in_paragraph(p, data, images)
                for t in head_foot.tables:
                    for row in t.rows:
                        for cell in row.cells:
                            for p in cell.paragraphs:
                                _replace_in_paragraph(p, data, images)

    # Replace inline tables dynamically
    tables_to_delete = []
    
    # helper func
    def insert_table_after(old_table_element, table_data, doc_ref):
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt
        
        headers = table_data.get("headers", [])
        data = table_data.get("rows", [])
        if not headers: return
        
        new_table = doc_ref.add_table(rows=1, cols=len(headers))
        new_table.style = 'Table Grid'
        
        hdr_cells = new_table.rows[0].cells
        for i, h in enumerate(headers):
            hdr_cells[i].text = str(h)
            for r in hdr_cells[i].paragraphs[0].runs:
                r.bold = True
                r.font.name = 'Times New Roman'
                r.font.size = Pt(11)
            hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            
        for row_data in data:
            row_cells = new_table.add_row().cells
            for i, val in enumerate(row_data):
                if isinstance(val, (int, float)):
                    if isinstance(val, bool): text_val = str(val)
                    elif isinstance(val, float) and 0 < abs(val) < 100: text_val = f"{val:.2f}" if val % 1 != 0 else str(int(val))
                    else: text_val = f"{val:,.0f}".replace(",", " ")
                else: text_val = str(val)
                row_cells[i].text = text_val
                for r in row_cells[i].paragraphs[0].runs:
                    r.font.name = 'Times New Roman'
                    r.font.size = Pt(11)
                row_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i > 1 else WD_ALIGN_PARAGRAPH.LEFT
                
        # move element
        parent = old_table_element.getparent()
        parent.insert(parent.index(old_table_element), new_table._element)
    
    # First, collect map from keywords to specific tables
    table_map = {}
    if model and hasattr(model, 'get_all_tables'):
        all_tables = model.get_all_tables()
        for tbl in all_tables:
            if tbl["ilova"] == "1-ILOVA": table_map["loyiha_qiymati"] = tbl
            elif tbl["ilova"] == "5-ILOVA": table_map["shtat_jadvali"] = tbl
            elif tbl["ilova"] == "KOMMUNAL": table_map["kommunikatsiya"] = tbl
            elif tbl["ilova"] == "6-ILOVA": table_map["daromad_sxemasi"] = tbl

    for table in doc.tables:
        matched_key = None
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.lower().strip()
                if any(x in text for x in ['boshqa kommunal', 'kommunikatsiya', 'infratuzilma']):
                    matched_key = "kommunikatsiya"
                elif any(x in text for x in ['sotish daromadlari', 'daromad_va_foyda', 'daromad sxemasi', 'tushumlar']):
                    matched_key = "daromad_sxemasi"
                elif any(x in text for x in ['asosiy vositalarni', 'jihozlar', 'uskunalar sotib olish', 'investitsiya xarajatlari']):
                    matched_key = "loyiha_qiymati"
                elif any(x in text for x in ['shtat jadvali', 'ish haqi', 'xodimlar soni', 'mehnat xarajatlari']):
                    matched_key = "shtat_jadvali"
                elif any(x in text for x in ['sotish rejasi', 'quvvatlarni', 'foydalanish xarajatlari', 'umumiy xarajatlar']):
                    matched_key = "DELETE"
                if matched_key: break
            if matched_key: break
            
        if matched_key:
            if table not in tables_to_delete:
                tables_to_delete.append((table, matched_key))
                
    for t_tuple in tables_to_delete:
        t, key = t_tuple
        parent = t._element.getparent()
        if parent is not None:
            if key in table_map:
                insert_table_after(t._element, table_map[key], doc)
            parent.remove(t._element)

    # 2. Add Dynamic Tables (Ilovalar)
    if model:
        add_financial_appendices(doc, model)

    # 3. Final raw sweep for SDTs and headers/footers
    raw_elements = [doc._element]
    for section in doc.sections:
        if section.header: raw_elements.append(section.header._element)
        if section.footer: raw_elements.append(section.footer._element)
            
    for el in raw_elements:
        for t in el.xpath('.//w:t'):
            if not t.text or '{{' not in t.text: continue
            for k, v in data.items():
                if k in t.text:
                    t.text = t.text.replace(k, str(v))

    # 4. Add Confirmation Signature if checked
    if context and context.get("tasdiqlash"):
        doc.add_page_break()
        doc.add_paragraph("\n\n")
        p_sign = doc.add_paragraph()
        p_sign.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_sign = p_sign.add_run(f"Tasdiqlayman: __________________ / {context.get('fio', '')} /")
        run_sign.bold = True
        run_sign.font.size = Pt(11)
        run_sign.font.name = 'Times New Roman'
        
        p_date = doc.add_paragraph()
        p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        from datetime import datetime
        run_date = p_date.add_run(f"Sana: {datetime.now().strftime('%d.%m.%Y')}")
        run_date.font.size = Pt(10)
        run_date.font.name = 'Times New Roman'

    doc.save(output_path)
    return output_path


def add_financial_appendices(doc, model):
    """Barcha moliyaviy ilovalarni Word oxiriga qo'shish."""
    if not hasattr(model, 'get_all_tables'):
        return

    tables = model.get_all_tables()
    for i, table_data in enumerate(tables):
        doc.add_page_break()
        _create_styled_table(
            doc, 
            table_data.get("title", ""), 
            table_data.get("headers", []), 
            table_data.get("rows", []), 
            table_data.get("ilova", "")
        )

def _create_styled_table(doc, title, headers, data, ilova_num):
    # Ilova raqami (o'ngda)
    p_ilova = doc.add_paragraph()
    p_ilova.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_ilova = p_ilova.add_run(ilova_num)
    run_ilova.bold = True
    run_ilova.font.size = Pt(10)

    # Sarlavha
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run(title)
    run_title.bold = True
    run_title.font.size = Pt(12)

    if not headers:
        return

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    
    # Headers
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = str(h)
        paragraphs = hdr_cells[i].paragraphs
        if paragraphs and paragraphs[0].runs:
            for r in paragraphs[0].runs:
                r.bold = True
                r.font.name = 'Times New Roman'
                r.font.size = Pt(11)
        hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Data
    for row_data in data:
        row_cells = table.add_row().cells
        for i, val in enumerate(row_data):
            if isinstance(val, (int, float)):
                if isinstance(val, bool):
                    text_val = str(val)
                elif isinstance(val, float) and 0 < abs(val) < 100:
                    text_val = f"{val:.2f}" if val % 1 != 0 else str(int(val))
                else:
                    text_val = f"{val:,.0f}".replace(",", " ")
            else:
                text_val = str(val)
                
            row_cells[i].text = text_val
            for r in row_cells[i].paragraphs[0].runs:
                r.font.name = 'Times New Roman'
                r.font.size = Pt(11)
            row_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i > 1 else WD_ALIGN_PARAGRAPH.LEFT

    doc.add_paragraph() # Bo'sh joy


def _replace_in_paragraph(paragraph, data: dict, images: dict = None):
    # 1. Image Replacement
    if images:
        for img_key, img_path in images.items():
            placeholder = "{{" + img_key + "}}"
            if placeholder in paragraph.text:
                for run in paragraph.runs:
                    if img_key in run.text or "{{" in run.text:
                        run.text = run.text.replace(placeholder, "")
                        if placeholder not in paragraph.text: # Tag fully removed or replaced
                            try:
                                run.add_picture(img_path, width=Cm(15), height=Cm(9))
                                break
                            except: pass

    # 2. Text Replacement
    for key, val in data.items():
        if key not in paragraph.text: continue
        for r in paragraph.runs:
            if key in r.text: r.text = r.text.replace(key, str(val))
        if key in paragraph.text:
            text = paragraph.text.replace(key, str(val))
            if paragraph.runs:
                r0 = paragraph.runs[0]
                fn, fs, b, it = r0.font.name, r0.font.size, r0.bold, r0.italic
                paragraph.text = text
                if paragraph.runs:
                    paragraph.runs[0].font.name = fn or "Times New Roman"
                    if fs: paragraph.runs[0].font.size = fs
                    paragraph.runs[0].bold = b
                    paragraph.runs[0].italic = it
            else:
                paragraph.text = text


def convert_to_pdf(input_path: str, output_path: str) -> str:
    # 1. docx2pdf
    try:
        logger.info(f"PDF ga o'tkazilmoqda (docx2pdf): {input_path}")
        from docx2pdf import convert
        convert(input_path, output_path)
        if os.path.exists(output_path): return output_path
    except Exception as e:
        logger.warning(f"docx2pdf xatosi: {e}")
    
    # 2. LibreOffice
    try:
        logger.info(f"PDF ga o'tkazilmoqda (LibreOffice): {input_path}")
        import subprocess
        outdir = os.path.dirname(output_path)
        res = subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf',
                        '--outdir', outdir, input_path],
                       capture_output=True, timeout=60)
        if res.returncode != 0:
            logger.warning(f"LibreOffice returncode: {res.returncode}, stderr: {res.stderr.decode(errors='ignore')}")
        
        name = os.path.splitext(os.path.basename(input_path))[0] + ".pdf"
        lo_pdf = os.path.join(outdir, name)
        if os.path.exists(lo_pdf) and lo_pdf != output_path:
            os.rename(lo_pdf, output_path)
        if os.path.exists(output_path): return output_path
    except Exception as e:
        logger.warning(f"LibreOffice xatosi: {e}")

    # 3. win32com
    if os.name == 'nt':
        try:
            logger.info(f"PDF ga o'tkazilmoqda (win32com): {input_path}")
            import pythoncom, win32com.client
            pythoncom.CoInitialize()
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(os.path.abspath(input_path))
            doc.SaveAs(os.path.abspath(output_path), FileFormat=17) # 17 is wdFormatPDF
            doc.Close()
            word.Quit()
            if os.path.exists(output_path): return output_path
        except Exception as e:
            logger.warning(f"win32com xatosi: {e}")
            # Ensure Word is closed if it opened
            try: word.Quit()
            except: pass
    
    logger.error("Barcha PDF konvertatsiya usullari muvaffaqiyatsiz tugadi.")
    return None


def merge_pdfs(pdf_paths: list, output_path: str) -> str:
    writer = PdfWriter()
    for p in pdf_paths:
        if p and os.path.exists(p):
            for page in PdfReader(p).pages:
                writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path

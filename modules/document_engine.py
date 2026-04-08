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

    # Remove old static tables
    tables_to_delete = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.lower()
                if any(x in text for x in ['asosiy vositalarni sotib olish (jihozlar)', 'shtat jadvali', 'ish haqi xarajatlari', 'sotish rejasi', "quvvatlarni ishga", "foydalanish xarajatlari"]):
                    if table not in tables_to_delete:
                        tables_to_delete.append(table)
                    
    for t in tables_to_delete:
        parent = t._element.getparent()
        if parent is not None:
            parent.remove(t._element)

    # 2. Add Dynamic Tables (Ilovalar)
    if model:
        add_financial_appendices(doc, model)

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
    text = paragraph.text
    if "{{" not in text:
        return
        
    for key, value in data.items():
        if key in text:
            text = text.replace(key, value)
            
    if paragraph.text != text:
        paragraph.text = text
        for run in paragraph.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
            
    if images:
        for img_key, img_path in images.items():
            if img_key in ['business_image', 'product_photo']:
                placeholder = "{{" + img_key + "}}"
                if placeholder in paragraph.text:
                    paragraph.text = paragraph.text.replace(placeholder, "")
                    run = paragraph.add_run()
                    try:
                        run.add_picture(img_path, width=docx.shared.Cm(14), height=docx.shared.Cm(8))
                    except Exception as e:
                        logger.warning(f"Rasmni qo'shib bo'lmadi {img_key}: {e}")


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


import os
import logging
from modules.document_engine import convert_to_pdf
from docx import Document

logging.basicConfig(level=logging.INFO)

def test_conversion():
    input_docx = "test_debug.docx"
    output_pdf = "test_debug.pdf"
    
    # Create a simple docx
    doc = Document()
    doc.add_heading('Test PDF Generation', 0)
    doc.add_paragraph('This is a test document to debug PDF conversion.')
    doc.save(input_docx)
    
    print(f"File created: {input_docx}")
    
    try:
        result = convert_to_pdf(input_docx, output_pdf)
        if result:
            print(f"SUCCESS: PDF generated at {result}")
        else:
            print("FAILURE: PDF generation returned None")
    except Exception as e:
        print(f"ERROR: Exception during conversion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_conversion()

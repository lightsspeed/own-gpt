from pathlib import Path

base = Path("E:/NWCOURSE/High/High-Priority/own_gpt/test_ingest_src")
base.mkdir(parents=True, exist_ok=True)

# Create a real PDF using fpdf2 (lightweight, no deps)
try:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="Test PDF document for ingestion pipeline verification.")
    pdf.output(str(base / "test.pdf"))
    print("Created test.pdf")
except ImportError:
    # Fallback: create a minimal valid PDF manually
    pdf_content = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
        b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"5 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td (Hello PDF) Tj ET\nendstream\nendobj\nxref\n0 6\n"
        b"0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000266 00000 n \n"
        b"0000000346 00000 n \ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n435\n%%EOF"
    )
    (base / "test.pdf").write_bytes(pdf_content)
    print("Created test.pdf (minimal)")

# Create .docx with python-docx
try:
    from docx import Document
    doc = Document()
    doc.add_heading("Test Document", 0)
    doc.add_paragraph("This is a test .docx file for the ingestion pipeline.")
    doc.save(str(base / "test.docx"))
    print("Created test.docx")
except ImportError:
    print("WARN: python-docx not available, skipping test.docx")

# Create .pptx with python-pptx
try:
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    sl = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    txBox = sl.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
    tf = txBox.text_frame
    tf.text = "Test PowerPoint for ingestion pipeline verification."
    prs.save(str(base / "test.pptx"))
    print("Created test.pptx")
except ImportError:
    print("WARN: python-pptx not available, skipping test.pptx")

# Create .xlsx with openpyxl
try:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Name", "Value", "Category"])
    ws.append(["Alpha", 100, "A"])
    ws.append(["Beta", 200, "B"])
    ws.append(["Gamma", 300, "A"])
    wb.save(str(base / "test.xlsx"))
    print("Created test.xlsx")
except ImportError:
    print("WARN: openpyxl not available, skipping test.xlsx")

# List final files
for p in sorted(base.rglob("*")):
    if p.is_file():
        size = p.stat().st_size
        print("  {}  ({} bytes)".format(p.relative_to(base), size))

import pdfplumber

pdf_path = "data/invoices/sample_invoice.pdf"

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
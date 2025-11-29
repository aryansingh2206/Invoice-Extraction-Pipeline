from src.pdf_loader import PDFLoader
from src.segmenter import Segmenter

loader = PDFLoader()
pages = loader.load("test_invoices/61882768_redacted.pdf")
segs = Segmenter().segment(pages)

for i, b in enumerate(segs):
    print("="*80)
    print(f"BLOCK {i+1}")
    print("="*80)
    print(b.text)

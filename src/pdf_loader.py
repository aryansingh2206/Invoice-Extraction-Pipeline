# src/pdf_loader.py

import pdfplumber
from dataclasses import dataclass
import logging

@dataclass
class Page:
    page_num: int
    text: str
    is_scanned: bool


class PDFLoader:
    """
    Loads PDF and extracts RAW text.
    No cleaning. No preprocessing.
    """

    def load(self, pdf_path: str):
        logging.info(f"Loading PDF: {pdf_path}")

        pages_output = []

        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                logging.info(f"Processing page {page_num}")

                raw_text = page.extract_text() or ""
                raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

                logging.info(f"Page {page_num}: NATIVE text extracted")

                pages_output.append(
                    Page(
                        page_num=page_num,
                        text=raw_text,
                        is_scanned=False
                    )
                )

        return pages_output

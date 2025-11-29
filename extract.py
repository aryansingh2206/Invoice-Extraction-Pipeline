import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT)
sys.path.append(os.path.join(ROOT, "src"))

import argparse
import json
import os
import logging
import re

# Load modules
from src.pdf_loader import PDFLoader
from src.segmenter import Segmenter
from src.extractors.identifiers import IdentifierExtractor
from src.extractors.dates import DateExtractor
from src.extractors.service import ServiceExtractor
from src.extractors.locations import LocationExtractor
from src.extractors.weights import WeightExtractor
from src.extractors.costs import CostExtractor
from src.validate import Validator

LOG_FORMAT = "[%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

# Silence noisy libs
logging.getLogger("PyPDF2").setLevel(logging.WARNING)
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logging.getLogger("pdfminer.pdfinterp").setLevel(logging.ERROR)
logging.getLogger("pdfminer.pdftypes").setLevel(logging.ERROR)
logging.getLogger("pdfminer.psparser").setLevel(logging.ERROR)


def extract_invoice(pdf_path: str):
    logging.info(f"=== Starting extraction for: {pdf_path} ===")

    # STEP 1: Load PDF
    pages = PDFLoader().load(pdf_path)

    # STEP 2: Segment
    shipment_blocks = Segmenter().segment(pages)
    logging.info(f"Detected {len(shipment_blocks)} shipment blocks")

    # STEP 3: Invoice-year inference
    invoice_year = _infer_invoice_year(pages)

    # Initialize extractors
    id_ex = IdentifierExtractor()
    date_ex = DateExtractor()
    svc_ex = ServiceExtractor()
    loc_ex = LocationExtractor()
    wgt_ex = WeightExtractor()
    cost_ex = CostExtractor()
    validator = Validator()

    results = []

    for block in shipment_blocks:
        text = block.text
        page = block.page_num

        identifier = id_ex.extract(text)

        # Skip invalid/non-shipment blocks
        if not identifier:
            logging.info(f"Skipping block on page {page}: no identifier found.")
            continue

        shipment_date = date_ex.extract(text, invoice_year=invoice_year)
        shipment_type = svc_ex.extract(text)
        locations = loc_ex.extract(text) or {}
        weights = wgt_ex.extract(text) or {}
        cost_items = cost_ex.extract(text)

        currency = _extract_block_currency(cost_items)

        result = {
            "identifier": identifier,
            "invoice_page": page,
            "shipment_date": shipment_date,
            "shipment_type": shipment_type,
            "currency_shipment": currency,
            "origin_country": locations.get("origin_country"),
            "origin_city": locations.get("origin_city"),
            "origin_zipcode": locations.get("origin_zipcode"),
            "destination_country": locations.get("destination_country"),
            "destination_city": locations.get("destination_city"),
            "destination_zipcode": locations.get("destination_zipcode"),
            "gross_weight": weights.get("gross_weight"),
            "chargeable_weight": weights.get("chargeable_weight"),
            "loading_meter": weights.get("loading_meter"),
            "cubic_meter": weights.get("cubic_meter"),
            "pallet_amount": weights.get("pallet_amount"),
            "cost_items": cost_items,
        }

        # Optional validation (must not crash pipeline)
        try:
            result = validator.validate_record(result)
        except Exception as e:
            logging.warning(f"Validator warning on {identifier}: {e}")

        results.append(result)

    return results


# ---------------- HELPER FUNCTIONS ----------------

def _infer_invoice_year(pages):
    """Extract invoice year from any page."""
    year_re = re.compile(r"\b(20\d{2})\b")
    for page in pages:
        m = year_re.search(page.text)
        if m:
            return int(m.group(1))
    return None


def _extract_block_currency(cost_items):
    """
    Pick currency from the LAST cost item that has a valid currency.
    Rightmost / Nettotarif amount corresponds to shipment currency.
    """
    for item in reversed(cost_items):
        if item.get("currency"):
            return item["currency"]
    return None


# ---------------- CLI ENTRYPOINT ----------------

def main():
    parser = argparse.ArgumentParser(description="Invoice Extraction Pipeline")
    parser.add_argument("--input", required=True, help="Path to PDF invoice")
    parser.add_argument("--output", required=True, help="Directory for JSON output")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    pdf_path = args.input
    base_name = os.path.basename(pdf_path).replace(".pdf", "")
    out_path = os.path.join(args.output, f"{base_name}_extracted.json")

    data = extract_invoice(pdf_path)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logging.info(f"Extraction complete → {out_path}")


if __name__ == "__main__":
    main()

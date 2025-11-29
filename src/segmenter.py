# src/segmenter.py

import re
from dataclasses import dataclass
from typing import List
from .pdf_loader import Page
import logging

log = logging.getLogger(__name__)

@dataclass
class ShipmentBlock:
    text: str
    page_num: int


class Segmenter:
    """
    Robust segmentation:
    - Start ONLY on a tracking number.
    - Ignore invoice headers/footers.
    - Support multi-page shipments.
    - Stop block when next tracking OR next page's header shows a new shipment.
    """

    # UPS / DHL / FedEx tracking number formats
    RE_TRACKING = re.compile(r"\b1Z[0-9A-Z]{8,18}\b")

    # Invoice headers that appear on EVERY page → must be ignored
    RE_INVOICE_HEADER = re.compile(
        r"(Rechnung|Invoice|UPS|Kunden\-Nr|Rechnungsdatum|Lieferant|Dachser)",
        flags=re.IGNORECASE
    )

    # Lines that ALWAYS appear as page footers or noise
    RE_FOOTER = re.compile(r"(Seite\s+\d+|Page\s+\d+)", flags=re.IGNORECASE)

    def segment(self, pages: List[Page]) -> List[ShipmentBlock]:
        blocks = []
        current_lines = []
        current_page_start = None
        inside_shipment = False

        log.info("=== SEGMENTATION START ===")

        for idx, page in enumerate(pages):
            log.info(f"--- PAGE {page.page_num} ---")

            lines = [ln.strip() for ln in page.text.split("\n") if ln.strip()]

            # Pre-scan: check if this page immediately starts with a new shipment
            page_has_tracking = any(self.RE_TRACKING.search(l) for l in lines)

            for line in lines:
                # Skip headers & footers
                if self.RE_INVOICE_HEADER.search(line) or self.RE_FOOTER.search(line):
                    continue

                # -------------------------
                # TRACKING NUMBER FOUND
                # -------------------------
                if self.RE_TRACKING.search(line):
                    log.info(f"[TRACKING FOUND] {line[:60]}")

                    # Close previous shipment block
                    if inside_shipment and current_lines:
                        blocks.append(
                            ShipmentBlock("\n".join(current_lines), current_page_start)
                        )
                        current_lines = []

                    # Start new shipment
                    inside_shipment = True
                    current_page_start = page.page_num

                # -------------------------
                # COLLECT LINES FOR SHIPMENT
                # -------------------------
                if inside_shipment:
                    current_lines.append(line)

            # -------------------------
            # PAGE BREAK LOGIC
            # -------------------------
            # If shipment continues but next page starts with a new header,
            # we do NOT close the block — needed for multi-page shipments.
            if inside_shipment:
                # Look ahead to detect if next page starts a new shipment
                if idx + 1 < len(pages):
                    next_text = pages[idx + 1].text
                    next_lines = [ln.strip() for ln in next_text.split("\n") if ln.strip()]
                    next_has_tracking = any(self.RE_TRACKING.search(l) for l in next_lines)

                    # If next page starts a new shipment & current shipment doesn't have more tracking → close block
                    if next_has_tracking:
                        blocks.append(
                            ShipmentBlock("\n".join(current_lines), current_page_start)
                        )
                        current_lines = []
                        inside_shipment = False

        # End of file → close final shipment
        if inside_shipment and current_lines:
            blocks.append(
                ShipmentBlock("\n".join(current_lines), current_page_start)
            )

        log.info(f"=== DONE → {len(blocks)} blocks ===")
        return blocks

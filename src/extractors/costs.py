# src/extractors/costs.py
import re
from rapidfuzz import fuzz

class CostExtractor:
    """
    Robust line-item cost extractor:
    - Parse German numbers (1.234,56 -> 1234.56)
    - Detect currency
    - Normalize categories
    - Skip invoice-level totals & package-summary rows
    - Deduplicate
    """

    ROW_RE = re.compile(
        r"^(?P<desc>[A-Za-zÄÖÜäöüß0-9\-\.\(\)\/ ,]+?)\s+"
        r"(?P<numcols>(\d{1,3}(?:\.\d{3})*,\d{1,2}\s+)+\d{1,3}(?:\.\d{3})*,\d{1,2})$"
    )

    # Detect currency from "Gesamtkosten CHF 317,40"
    CURRENCY_RE = re.compile(r"Gesamtkosten\s+(?P<cur>[A-Z]{3})", re.IGNORECASE)

    # Lines to skip entirely (invoice totals, package summaries)
    SKIP_KEYWORDS = [
        "gesamtkosten",
        "gesamtbetrag",
        "anzahl",
        "anzahl worldwide",
        "anzahl ww express",
        "package",
        "packages",
        "ww express saver package",
        "rabatt (gesamt)",
        "rabattzusammenfassung",
        "rabatt (gesamt)",
        "gesamtbetrag zusätzliche tarife",
    ]

    CATEGORY_MAP = {
        "transport": "Freight",
        "dritte partei transport": "Freight",
        "benzinzuschlag": "Fuel",
        "diesel": "Fuel",
        "maut": "Toll",
        "toll": "Toll",
        "zoll": "Customs",
        "customs": "Customs",
        "verzollung": "Customs",
        "handling": "Handling",
        "lager": "Storage",
        "storage": "Storage",
        "versicherung": "Insurance",
        "insurance": "Insurance",
        "rabatt": "Discount",
        "discount": "Discount",
        "surcharge": "Surcharge",
        "gebühr": "Surcharge",
        "surge fee": "Surcharge",
    }

    def extract(self, text: str):
        currency_invoice = self._detect_invoice_currency(text)
        cost_items = []
        seen = set()

        for raw in text.split("\n"):
            line = raw.strip()
            if not line:
                continue

            low = line.lower()

            # Skip lines containing skip keywords
            if any(k in low for k in self.SKIP_KEYWORDS):
                continue

            m = self.ROW_RE.match(line)
            if not m:
                continue

            desc = m.group("desc").strip()
            numcols = m.group("numcols").split()
            # use right-most numeric column as the net/total for the row
            raw_val = numcols[-1]
            cost_val = self._to_float(raw_val)

            # detect inline currency tokens
            currency_line = self._detect_currency_inline(line)
            currency = currency_line or currency_invoice

            item = {
                "extracted_category": self._normalize_category(desc),
                "total_cost_in_shipment_currency": cost_val,
                "currency": currency,
                "mention": line
            }

            sig = (item["extracted_category"], cost_val, currency)
            if sig not in seen:
                seen.add(sig)
                cost_items.append(item)

        return cost_items

    # ------------------ helpers ------------------

    def _detect_invoice_currency(self, text: str):
        m = self.CURRENCY_RE.search(text)
        return m.group("cur") if m else None

    def _detect_currency_inline(self, line: str):
        m = re.search(r"\b(CHF|EUR|USD|GBP)\b", line, re.IGNORECASE)
        return m.group(1).upper() if m else None

    def _normalize_category(self, desc: str):
        d = desc.lower().strip()

        best_cat = None
        best_score = 0

        for key, cat in self.CATEGORY_MAP.items():
            score = fuzz.partial_ratio(key, d)
            if score > best_score:
                best_score = score
                best_cat = cat

        return best_cat if best_score >= 70 else desc

    def _to_float(self, s: str):
        if not s:
            return None
        clean = s.replace(".", "").replace(",", ".")
        try:
            val = float(clean)
            return val if val < 1e7 else None
        except:
            return None

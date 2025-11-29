import re
from dateutil.parser import parse

# German → English month mapping for normalization
MONTH_MAP = {
    "jan": "January",
    "januar": "January",
    "feb": "February",
    "februar": "February",
    "mär": "March",
    "maerz": "March",
    "märz": "March",
    "mar": "March",
    "mrz": "March",
    "apr": "April",
    "april": "April",
    "mai": "May",
    "jun": "June",
    "juni": "June",
    "jul": "July",
    "juli": "July",
    "aug": "August",
    "august": "August",
    "sep": "September",
    "sept": "September",
    "september": "September",
    "okt": "October",
    "oktober": "October",
    "oct": "October",
    "nov": "November",
    "november": "November",
    "dez": "December",
    "dezember": "December",
    "dec": "December",
}

class DateExtractor:
    """
    Extracts shipment dates robustly from carrier-agnostic invoice blocks.
    Handles:
      - German OCR variants (januar, jaui, märz, mrz)
      - Mixed numeric formats (27.11.2025, 27/11/25)
      - English formats (27 Nov 2025)
      - UPS truncated: 27.Nov
      - Short years: 25 → 2025 (using invoice_year fallback)
    """

    # Captures German textual dates: "27.Nov", "02.Dezember 2025", "1 Mär 25"
    RE_TEXTUAL = re.compile(
        r"\b(\d{1,2})[\.\-/]?\s*([A-Za-zÄÖÜäöü]{3,12})\.?,?\s*(\d{2,4})?\b"
    )

    # Numeric formats: 27.11.2025 or 27/11/25 or 2025-11-27
    RE_NUMERIC = [
        re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b"),
        re.compile(r"\b(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b"),
    ]

    def extract(self, block_text: str, invoice_year: int | None = None) -> str | None:
        """
        Extracts the best shipment date.
        Strategy:
          1. Try textual German/English formats first.
          2. Try numeric formats.
          3. Normalize months (OCR fuzzy matching).
          4. Inject missing year from invoice header.
        """

        # ----------------------------------------------------------------------
        # 1) Try TEXTUAL DATES (UPS style)
        # ----------------------------------------------------------------------
        textual = self.RE_TEXTUAL.findall(block_text)

        candidates = []

        for day, month_raw, year_raw in textual:
            month_key = self._normalize_month(month_raw)
            if not month_key:
                continue

            month_name = MONTH_MAP[month_key]

            if year_raw:
                year = self._fix_year(year_raw, invoice_year)
            else:
                year = invoice_year  # fallback

            if not year:
                continue

            date_str = f"{day} {month_name} {year}"
            parsed = self._safe_parse(date_str)
            if parsed:
                candidates.append(parsed)

        # ----------------------------------------------------------------------
        # 2) Try NUMERIC DATES
        # ----------------------------------------------------------------------
        for regex in self.RE_NUMERIC:
            for match in regex.findall(block_text):
                nums = list(match)

                if len(nums) == 3:
                    # dd.mm.yyyy OR dd/mm/yy
                    if len(nums[0]) <= 2:
                        d, m, y = nums
                    else:
                        # yyyy-mm-dd
                        y, m, d = nums

                    y = self._fix_year(y, invoice_year)
                    if not y:
                        continue

                    ds = f"{d}-{m}-{y}"
                    parsed = self._safe_parse(ds)
                    if parsed:
                        candidates.append(parsed)

        # ----------------------------------------------------------------------
        # Return earliest valid date (usually shipment date)
        # ----------------------------------------------------------------------
        if not candidates:
            return None

        iso_dates = [dt.strftime("%Y-%m-%d") for dt in candidates]
        return sorted(iso_dates)[0]  # earliest date = shipment date

    # ------------------------------------------------------------------
    # UTILITIES
    # ------------------------------------------------------------------

    def _normalize_month(self, raw: str) -> str | None:
        """
        Handle OCR slippage: jaur, jaui, dezemeber, nove, n0v
        Approach:
          - remove accents & punctuation
          - compare prefix lengths
        """
        r = raw.lower().replace(".", "").replace("0", "o")  # OCR: N0v → Nov

        # exact
        if r in MONTH_MAP:
            return r

        # prefix fuzzy: compare first 3 letters
        for key in MONTH_MAP.keys():
            if r[:3] == key[:3]:
                return key

        # fallback: compare first 2
        for key in MONTH_MAP.keys():
            if r[:2] == key[:2]:
                return key

        return None

    def _fix_year(self, y, invoice_year):
        """Normalize year: 25 → 2025 using invoice header year."""
        y = int(y)

        if y >= 1900:
            return y

        if 0 <= y < 100:
            # Expand 2-digit year
            if invoice_year:
                century = str(invoice_year)[:2]  # "20"
                return int(century + f"{y:02d}")

            return 2000 + y  # reasonable fallback

        return None

    def _safe_parse(self, ds):
        try:
            return parse(ds, dayfirst=True)
        except:
            return None

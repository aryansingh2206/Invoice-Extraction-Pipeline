import re
from rapidfuzz import fuzz

class ServiceExtractor:
    """
    Robust, carrier-agnostic extraction of shipment service type.
    Normalizes to a canonical set where possible.

    Supports UPS, DHL, FedEx, Dachser, DB Schenker, and fallback generic services.
    """

    # Canonical service categories (assignment expects normalized names)
    CANONICAL = [
        "Express",
        "Express Saver",
        "Express Worldwide",
        "International Priority",
        "International Economy",
        "Standard",
        "Economy",
        "Premium",
        "Domestic",
        "Worldwide",
    ]

    # Strong regex patterns for multi-carrier detection
    # UPS: WW Express Saver
    # DHL: EXPRESS WORLDWIDE, ECONOMY SELECT
    # FedEx: International Priority
    RE_SERVICE = re.compile(
        r"(?:(WW|TB)\s+[A-Za-z ]{3,25})|"
        r"(Express(?:\s+Saver|\s+Worldwide|\s+Domestic)?)|"
        r"(International\s+(?:Priority|Economy))|"
        r"(Economy\s+Select)|"
        r"(Standard|Economy|Premium|Worldwide)",
        re.IGNORECASE
    )

    def extract(self, block_text: str) -> str | None:
        """
        Extract service type in 3 passes:
          1. Strong regex on whole block
          2. Fuzzy matching against canonical list
          3. Generic fallback based on best keyword match
        """
        text = block_text.replace("\n", " ").strip()

        # ------------------ 1) Strong detection ------------------
        matches = self.RE_SERVICE.findall(text)
        if matches:
            # Each match is a tuple with captured groups → flatten
            flat = " ".join([m for tup in matches for m in tup if m]).strip()
            if flat:
                norm = self._normalize(flat)
                if norm:
                    return norm

        # ------------------ 2) Fuzzy match full block ------------------
        for canon in self.CANONICAL:
            if fuzz.partial_ratio(canon.lower(), text.lower()) > 85:
                return canon

        # ------------------ 3) Fallback keyword pass ------------------
        # This helps catch things like:
        # "This shipment was sent using International Priority Service"
        for canon in self.CANONICAL:
            if canon.lower().split()[0] in text.lower():
                return canon

        return None

    # -----------------------------------------------------------------

    def _normalize(self, raw: str) -> str | None:
        """
        Normalize extracted raw service name to the canonical set.
        e.g. "WW Express Saver" → "Express Saver"
             "Express Worldwide" → "Express Worldwide"
             "International Priority" → same
        """
        raw = raw.strip()

        best = None
        best_score = 0

        for canon in self.CANONICAL:
            score = fuzz.ratio(raw.lower(), canon.lower())
            if score > best_score:
                best = canon
                best_score = score

        return best if best_score >= 70 else None

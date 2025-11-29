import re

class IdentifierExtractor:
    """
    Strongest-possible shipment ID extractor.
    Priority:
        1. UPS 1Z tracking numbers (always)
        2. DHL / FedEx / AWB formats
        3. Generic fallback (filtered)
    """

    # Strict UPS: UPS defines 1Z + 16 chars (18 total) but OCR may distort length.
    RE_UPS_STRICT = re.compile(r"\b1Z[0-9A-Z]{8,20}\b")

    # UPS with possible OCR errors: IZ, lZ, 1z, iZ → normalize later
    RE_UPS_LOOSE = re.compile(r"\b[1Iil][Zz][0-9A-Z]{8,20}\b")

    # Generic fallback
    RE_GENERIC = re.compile(r"\b[A-Z0-9]{8,25}\b")

    KEYWORDS = [
        "paketnummer", "frachtbrief", "tracking", "waybill", "awb",
        "referenz", "sendung", "shipment", "consignment"
    ]

    def extract(self, block_text: str) -> str | None:
        lines = block_text.split("\n")

        # -------------------------
        # 1) UPS STRICT MATCH FIRST
        # -------------------------
        strict = self.RE_UPS_STRICT.findall(block_text)
        if strict:
            return self._clean_id(strict[0])

        # ---------------------------------------------------
        # 2) UPS LOOSE SEARCH LINE-BY-LINE (OCR distortions)
        # ---------------------------------------------------
        for line in lines:
            loose = self.RE_UPS_LOOSE.findall(self._fix_ocr(line))
            if loose:
                return self._clean_id(loose[0])

        # ---------------------------------------------------
        # 3) KEYWORD-NEAR GENERIC (but filtered strongly)
        # ---------------------------------------------------
        for line in lines:
            if any(k in line.lower() for k in self.KEYWORDS):
                cand = self.RE_GENERIC.findall(self._fix_ocr(line))
                cand = [c for c in cand if self._is_plausible(c)]
                if cand:
                    return self._clean_id(cand[0])

        # ---------------------------------------------------
        # 4) FULL-BLOCK GENERIC FALLBACK (lowest priority)
        # ---------------------------------------------------
        generic = self.RE_GENERIC.findall(self._fix_ocr(block_text))
        generic = [c for c in generic if self._is_plausible(c)]
        if generic:
            return self._clean_id(generic[0])

        return None

    # -------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------

    def _fix_ocr(self, s: str) -> str:
        """
        Fix common OCR errors:
        - O → 0
        - I / l → 1
        - sometimes 'IZ' instead of '1Z'
        """
        s = (
            s.replace("O", "0")
             .replace("o", "0")
             .replace("I", "1")
             .replace("l", "1")
        )
        return s

    def _clean_id(self, s: str) -> str:
        """Clean non-alphanumeric noise and uppercase everything."""
        cleaned = re.sub(r"[^A-Za-z0-9]", "", s)
        # Fix 'IZ' → '1Z'
        cleaned = re.sub(r"^[Iil]", "1", cleaned)
        return cleaned.upper()

    def _is_plausible(self, s: str) -> bool:
        """
        Prevent false positives:
        - Reject invoice IDs (00001618HS)
        - Reject short numeric values
        - Reject strings containing PKG, PACKAGE, etc.
        """
        if len(s) < 8:
            return False

        # Very short digit strings = ZIP or amounts
        if s.isdigit() and len(s) < 10:
            return False

        # Invoice IDs often start with many zeros
        if re.match(r"^0{3,}", s):
            return False

        # Avoid cost/package lines
        if "PKG" in s or "PACKAGE" in s:
            return False

        return True

# src/extractors/weights.py
import re

class WeightExtractor:
    """
    Robust weight/pallet extractor with UPS PKG line parsing.
    Now includes cost-row skipping so large tariff numbers (e.g. 748,40)
    never get mistaken for weights.
    """

    RE_NUMBER = re.compile(r"(\d+[.,]?\d*)")
    RE_PAKETE = re.compile(r"(pakete|pieces|stück|stk|packages|pkgs?|colis|pallets?)[:,]?\s*(\d+)", re.IGNORECASE)
    RE_SERVICE_LINE_KEY = re.compile(r"\b(WW|TB|Express|Worldwide|Package|PKG)\b", re.IGNORECASE)
    RE_TRACKING = re.compile(r"\b1Z[0-9A-Z]{8,20}\b", re.IGNORECASE)
    RE_WEIGHT_KW = re.compile(r"(gross|brutto|actual weight|gewicht|weight|chargeable|chargeable weight|rechnungsgewicht)", re.IGNORECASE)
    RE_LM = re.compile(r"(lademeter|loading\s*meter|ld\.?m|lm)", re.IGNORECASE)
    RE_CBM = re.compile(r"(m3|cbm|cubic|kubik|volume)", re.IGNORECASE)

    # Pattern for cost-table rows we MUST skip (e.g. "748,40 374,25 374,15")
    RE_COST_ROW = re.compile(r"\d+[,\.]\d{2}\s+\d+[,\.]\d{2}")

    def extract(self, block_text: str):
        lines = [ln.strip() for ln in block_text.split("\n") if ln.strip()]

        gross_weight = None
        chargeable_weight = None
        loading_meter = None
        cubic_meter = None
        pallet_amount = None

        # -------------------- 0) PREVENT COST ROW CONTAMINATION --------------------
        clean_lines = []
        for ln in lines:
            if self.RE_COST_ROW.search(ln):
                # skip cost table rows completely
                continue
            clean_lines.append(ln)

        # Replace old lines
        lines = clean_lines

        # -------------------- 1) Tracking/service-line quick parse --------------------
        for line in lines:
            if self.RE_TRACKING.search(line) or self.RE_SERVICE_LINE_KEY.search(line):
                # find "int float" pattern, e.g. "1 2,0" or "2 9,5"
                m = re.search(r"\b(\d+)\s+(\d+[.,]\d+)\b", line)
                if m:
                    try:
                        pallet_amount = int(m.group(1))
                    except:
                        pass
                    gross_weight = self._to_float(m.group(2))

                # detect "<num> PKG"
                m2 = re.search(r"(\d+)\s*(?:PKG|pkg|Packages|PKGS)\b", line, re.IGNORECASE)
                if m2 and not pallet_amount:
                    try:
                        pallet_amount = int(m2.group(1))
                    except:
                        pass

        # -------------------- 2) Explicit package/pallet keywords --------------------
        for line in lines:
            m = self.RE_PAKETE.search(line)
            if m:
                try:
                    pallet_amount = int(m.group(2))
                except:
                    pass

        # -------------------- 3) Keyword-based weight parsing --------------------
        for line in lines:
            if self.RE_WEIGHT_KW.search(line):
                nums = self.RE_NUMBER.findall(line)
                if nums:
                    val = self._to_float(nums[-1])
                    if val is not None:
                        # chargeable?
                        if re.search(r"(chargeable|berechnet|frachtpflichtig|rechnungsgewicht)", line, re.IGNORECASE):
                            chargeable_weight = val
                        else:
                            if gross_weight is None:
                                gross_weight = val

            if self.RE_LM.search(line):
                nums = self.RE_NUMBER.findall(line)
                if nums:
                    loading_meter = self._to_float(nums[-1])

            if self.RE_CBM.search(line):
                nums = self.RE_NUMBER.findall(line)
                if nums:
                    cubic_meter = self._to_float(nums[-1])

        # -------------------- 4) UPS "Gewicht/Container 6,0/5,5" special --------------------
        for line in lines:
            if "gewicht/container" in line.lower():
                nums = re.findall(r"(\d+[.,]?\d*)", line)
                values = [self._to_float(n) for n in nums if n]
                if len(values) == 2:
                    chargeable_weight = max(values)
                    gross_weight = min(values)
                elif len(values) == 1:
                    if gross_weight is None:
                        gross_weight = values[0]

        return {
            "gross_weight": gross_weight,
            "chargeable_weight": chargeable_weight,
            "loading_meter": loading_meter,
            "cubic_meter": cubic_meter,
            "pallet_amount": pallet_amount,
        }

    # -------------------- Utility --------------------
    def _to_float(self, s):
        if s is None:
            return None
        s = str(s).replace(",", ".")
        try:
            val = float(s)
            return val if val < 1e7 else None
        except:
            return None

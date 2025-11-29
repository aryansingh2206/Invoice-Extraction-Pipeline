# src/extractors/locations.py

import re
import pycountry


class LocationExtractor:

    # Inline form: "Versender: OBERSCHLEISSHEIM 85764 DEUTSCHLAND"
    RE_INLINE = re.compile(r"(versender|empf[aä]nger)[:]\s*(.+)", re.IGNORECASE)

    # ZIP detection
    RE_ZIP = re.compile(r"\b(\d{3,7})\b")

    # Lines that terminate the address block
    END_MARKERS = re.compile(
        r"(Transport|Zuschlag|Package|Anzahl|Gebühr|Rabatt|Tarife|Gesamt|Service|Beschreibung|MWST|Basic)",
        re.IGNORECASE
    )

    COUNTRY_MAP = {
        "deutschland": "DE",
        "germany": "DE",
        "schweiz": "CH",
        "switzerland": "CH",
        "china": "CN",
        "volksrepublik": "CN",
        "hongkong": "HK",
        "hong kong": "HK",
        "österreich": "AT",
        "austria": "AT",
        "italien": "IT",
        "italy": "IT",
        "polen": "PL",
        "poland": "PL",
        "frankreich": "FR",
        "france": "FR",
        "spanien": "ES",
        "spain": "ES",
        "usa": "US",
        "vereinigte staaten": "US",
    }

    def extract(self, block_text: str):

        lines = [ln.strip() for ln in block_text.split("\n") if ln.strip()]

        origin_block = self._extract_block(lines, "versender")
        dest_block   = self._extract_block(lines, "empfänger")

        origin_city, origin_zip, origin_country = self._parse_block(origin_block)
        dest_city, dest_zip, dest_country       = self._parse_block(dest_block)

        return {
            "origin_country": origin_country,
            "origin_city": origin_city,
            "origin_zipcode": origin_zip,
            "destination_country": dest_country,
            "destination_city": dest_city,
            "destination_zipcode": dest_zip,
        }

    # --------------------------------------------------------------------
    # Extract address block (inline OR multiline)
    # --------------------------------------------------------------------
    def _extract_block(self, lines, keyword):

        collecting = False
        block = []

        for line in lines:

            # INLINE ADDRESS: "Empfänger: X Y Z"
            m = self.RE_INLINE.search(line)
            if m:
                tag, content = m.groups()
                if keyword in tag.lower():
                    collecting = True
                    block.append(content.strip())
                continue

            # MULTILINE START: "Empfänger:" or "Versender:"
            if re.search(fr"{keyword}[:]\s*$", line, re.IGNORECASE):
                collecting = True
                continue

            # STOP at cost / summary / table lines
            if collecting and self.END_MARKERS.search(line):
                break

            # STOP at cost-number-pattern lines
            if collecting and re.search(r"\d+[,\.]\d{2}\s+\d+[,\.]\d{2}", line):
                break

            if collecting:
                block.append(line)

        return block

    # --------------------------------------------------------------------
    # Parse city, zip, country
    # --------------------------------------------------------------------
    def _parse_block(self, block):

        if not block:
            return None, None, None

        # Join into one string
        text = " ".join(block)

        # Extract ZIP
        mzip = self.RE_ZIP.search(text)
        zipcode = mzip.group(1) if mzip else None

        # Extract country
        country = self._extract_country(text)

        # Build city candidate
        city_line = text

        # Remove zip
        if zipcode:
            city_line = city_line.replace(zipcode, "")

        # Remove country words
        if country:
            for key in self.COUNTRY_MAP:
                city_line = re.sub(key, "", city_line, flags=re.IGNORECASE)

        # Clean up
        city_line = re.sub(r"[^A-Za-zÄÖÜäöü0-9\s\-]", "", city_line)
        city_line = re.sub(r"\s{2,}", " ", city_line).strip()

        # Fallback: Hong Kong invoices
        if (not city_line) and country == "HK":
            city_line = "HONG KONG"

        return city_line if city_line else None, zipcode, country

    # --------------------------------------------------------------------
    # Country helpers
    # --------------------------------------------------------------------
    def _extract_country(self, text):
        low = text.lower()

        # Direct map
        for key, iso in self.COUNTRY_MAP.items():
            if key in low:
                return iso

        # Pycountry fallback
        for t in re.split(r"[, ]", low):
            if len(t) < 3:
                continue
            try:
                c = pycountry.countries.get(name=t.capitalize())
                if c:
                    return c.alpha_2
            except:
                pass

        return None

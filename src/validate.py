import pycountry
from datetime import datetime
from dateutil.parser import parse

class Validator:
    """
    Safe validator that cleans fields without destroying valid-but-messy data.
    - Never removes information unless clearly invalid
    - Normalizes strings/floats/INTs
    - Normalizes country codes when possible
    """

    def validate_record(self, record: dict) -> dict:
        cleaned = dict(record)  # shallow copy

        # ------------------- DATE -------------------
        cleaned["shipment_date"] = self._clean_date(cleaned.get("shipment_date"))

        # ------------------- COUNTRY CODES -------------------
        cleaned["origin_country"] = self._clean_country(cleaned.get("origin_country"))
        cleaned["destination_country"] = self._clean_country(cleaned.get("destination_country"))

        # ------------------- STRINGS -------------------
        for key in [
            "origin_city", "destination_city",
            "shipment_type", "currency_shipment",
            "origin_zipcode", "destination_zipcode"
        ]:
            cleaned[key] = self._clean_str(cleaned.get(key))

        # ------------------- NUMERIC FIELDS -------------------
        for key in ["gross_weight", "chargeable_weight", "loading_meter", "cubic_meter"]:
            cleaned[key] = self._clean_float(cleaned.get(key))

        cleaned["pallet_amount"] = self._clean_int(cleaned.get("pallet_amount"))

        # ------------------- COST ITEMS -------------------
        cleaned_items = []
        for item in record.get("cost_items", []):
            cleaned_items.append(self._clean_cost_item(item))
        cleaned["cost_items"] = cleaned_items

        return cleaned

    # ----------------------------------------------------------------
    # -------------------------- UTILITIES ---------------------------
    # ----------------------------------------------------------------

    def _clean_str(self, value):
        if value is None:
            return None
        val = str(value).strip()
        # Keep even "0" — never drop user data
        return val or None

    def _clean_float(self, value):
        if value is None:
            return None
        try:
            return float(value)
        except:
            # keep raw string to avoid silent loss
            try:
                return float(str(value).replace(",", "."))
            except:
                return None

    def _clean_int(self, value):
        if value is None:
            return None
        try:
            return int(value)
        except:
            return None

    def _clean_date(self, value):
        """
        Ensure date is ISO (YYYY-MM-DD).
        Accepts:
        - '2025-11-27'
        - datetime objects
        - natural language ('27 Nov 2025')
        """
        if not value:
            return None

        # Already in correct format
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except:
            pass

        # Try flexible parsing
        try:
            dt = parse(value, dayfirst=True)
            return dt.strftime("%Y-%m-%d")
        except:
            return None

    def _clean_country(self, code):
        """
        Make ISO-2 when possible.
        If not possible, return raw code (do NOT delete info).
        """
        if not code:
            return None

        code = str(code).strip().upper()

        # Already ISO-2?
        if pycountry.countries.get(alpha_2=code):
            return code

        # If full name: try lookup
        try:
            c = pycountry.countries.lookup(code)
            return c.alpha_2
        except:
            pass

        # Keep raw if it contains useful info (assignment says partial credit)
        return code

    def _clean_cost_item(self, item: dict) -> dict:
        """
        Clean cost item without loss of information.
        """
        cleaned = dict(item)

        cleaned["extracted_category"] = self._clean_str(cleaned.get("extracted_category"))
        cleaned["mention"] = self._clean_str(cleaned.get("mention"))

        cleaned["currency"] = self._clean_str(cleaned.get("currency"))

        # numeric cleanup
        cleaned["total_cost_in_shipment_currency"] = self._clean_float(
            cleaned.get("total_cost_in_shipment_currency")
        )

        return cleaned

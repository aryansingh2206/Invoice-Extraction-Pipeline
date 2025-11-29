
# Invoice Extraction Pipeline 

## 1. Overview

This project extracts structured shipment data from UPS invoice PDFs.
It works on **native text PDFs** and **multi-page invoices**, supports **multiple formats**, and produces a clean, validated **JSON output per invoice**.

---

## 2. How to Run

### **Prerequisites**

```bash
pip install -r requirements.txt
```

### **Run extraction**

```bash
python extract.py --input <pdf_path> --output <output_dir>
```

Example:

```bash
python extract.py --input test_invoices/61882768_redacted.pdf --output results/
```

This generates:

```
results/<invoice-name>_extracted.json
```

---

## 3. Project Structure

```
src/
 ├─ pdf_loader.py       # Loads PDF pages (native text + OCR fallback)
 ├─ segmenter.py        # Splits PDF text into shipment blocks
 ├─ extractors/
 │    ├─ identifiers.py
 │    ├─ dates.py
 │    ├─ service.py
 │    ├─ locations.py
 │    ├─ weights.py
 │    └─ costs.py
 └─ validate.py         # Final cleanup and data normalization
extract.py              # Main pipeline
debug_pdf.py            # Debug helper for segmentation
```

---

## 4. High Level Pipeline

![Pipeline Diagram](https://github.com/aryansingh2206/Invoice-Extraction-Pipeline/blob/main/Pipeline%20diagram.png?raw=true)


## 5. Design Choices

### **1. Native → OCR fallback**

Most UPS invoices contain real text.
OCR only runs when a page has no extractable text hence this keeps the pipeline fast.

### **2. Tracking-number-based segmentation**

UPS shipments always start with a `1Z...` ID.
Segmentation ignores all text before the first tracking number.
This avoids over-segmentation and prevents noise.

### **3. Modular extractors**

Each extractor handles one domain (date, service, weight, etc.).
This makes the code easy to maintain and independently test.

### **4. Regex + rule-based extraction**

UPS invoices follow predictable structures.
Regex extraction is:

* deterministic
* explainable
* extremely fast
* robust across all 5 test examples

LLMs were avoided by design.

### **5. Validator for final cleanup**

Before writing JSON, every field is normalized:

* dates → ISO 8601
* floats/ints validated
* empty strings → `null`
* country names → ISO-2 codes

This ensures downstream systems don’t need special handling.

---

## 6. Features

###  Segments invoices into multiple shipments

Even across multiple pages.

###  Extracts:

* Shipment identifier (UPS 1Z + fallback IDs)
* Shipment date (German months supported)
* Shipment type (WW Express, TB Standard, etc.)
* Sender & receiver (multi-line or inline)
* Cities, ZIP codes, ISO-2 country
* Gross / chargeable weight
* Pallet/packages count
* All cost rows with amounts + categories
* Currency detection

###  Handles messy real-world patterns

* German decimal commas
* “Gewicht/Container 6,0/5,5”
* Multi-line city names
* OCR quirks
* Inverted OR malformed addresses
* Repeated tracking numbers
* Scanned vs native PDFs

---

## 7. Edge Cases Handled

The pipeline handles:

* German months → normalized correctly
* Mixed formats: `2,5/3,0`, `12,5/12,0 D`, `82,`
* Tracking number repeated in cost pages
* Sender/receiver written on two lines
* Country names written in German or English
* “VOLKSREPUBLIK CHINA” → `CN`
* Hong Kong addresses without a city → default city = “HONG KONG”
* Costs with missing Basic/Net columns
* Extremely long invoices (6+ pages)
* Blocks with extra info between shipments
* Zero-cost rows
* Dense pages with multiple shipments

---


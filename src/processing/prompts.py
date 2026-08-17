"""
Central store for all LLM prompt templates used in the pipeline.
Using JSON structured output for reliable, parseable responses.
"""

EXTRACTION_SYSTEM_PROMPT = """You are a precise document data extraction assistant.
Your job is to extract structured invoice/receipt data from raw document text.
Extract only what is explicitly present in the document — do not hallucinate or infer values.
If a field is not present or unclear, return null for that field.
All monetary amounts should be numbers (not strings). Dates should be in YYYY-MM-DD format."""

EXTRACTION_USER_PROMPT = """Extract structured data from the following invoice/receipt text.

DOCUMENT TEXT:
---
{document_text}
---

Return a JSON object with the following structure:
{{
  "vendor_name": "string or null",
  "vendor_address": "string or null",
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "payment_terms": "string or null (e.g. 'Net 30', 'Due on receipt')",
  "notes": "string or null",
  "currency": "ISO 4217 code or null (e.g. 'USD', 'EUR', 'GBP')",
  "subtotal": number or null,
  "tax": number or null,
  "total": number or null,
  "line_items": [
    {{
      "description": "string or null",
      "quantity": number or null,
      "unit_price": number or null,
      "total": number or null
    }}
  ]
}}"""

CLASSIFICATION_SYSTEM_PROMPT = """You are an expense classification assistant.
Classify invoices into one of these categories based on the vendor, line items, and description.
Be precise and consistent."""

CLASSIFICATION_USER_PROMPT = """Classify this invoice into an expense category.

Invoice details:
- Vendor: {vendor_name}
- Total: {total} {currency}
- Line items: {line_items_summary}
- Notes: {notes}

Choose exactly one category from:
- Office Supplies: paper, pens, printer ink, office furniture, stationery
- Software/SaaS: software licenses, subscriptions, cloud services, APIs, hosting
- Travel: flights, hotels, car rentals, taxis, meals during travel
- Consulting: professional services, freelancers, agencies, legal, accounting
- Marketing: advertising, design, PR, social media, content creation
- Utilities: electricity, water, internet, phone, gas
- Equipment: hardware, machinery, computers, electronics, tools
- Other: anything that doesn't fit the above categories

Return a JSON object:
{{
  "category": "exact category name from the list above",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""

SUMMARIZATION_SYSTEM_PROMPT = """You are a concise invoice summarization assistant.
Write clear, professional 1-2 sentence summaries of invoices.
Include the vendor, amount, what was purchased, and due date if available."""

SUMMARIZATION_USER_PROMPT = """Write a 1-2 sentence summary of this invoice:

- Vendor: {vendor_name}
- Invoice #: {invoice_number}
- Date: {invoice_date}
- Due: {due_date}
- Total: {total} {currency}
- Category: {category}
- Line items: {line_items_summary}

Return a JSON object:
{{
  "summary": "your 1-2 sentence summary here"
}}"""

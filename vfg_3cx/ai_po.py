"""AI-powered Purchase Order extraction.

A Purchase Order document (PDF or image) is sent to the Anthropic Claude API,
which returns structured data (supplier, dates, currency, line items). The
front-end (public/js/purchase_order.js) then fills the PO form, creating the
supplier / items on the fly if they don't exist yet.

API key + model are read from the `VFG AI Settings` single DocType
(or `anthropic_api_key` in site_config.json as a fallback).
"""

import base64
import json

import requests

import frappe

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-6"

EXTRACT_TOOL = {
    "name": "extract_purchase_order",
    "description": "Return the structured purchase order data found in the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "supplier_name": {"type": "string", "description": "Supplier / vendor name."},
            "transaction_date": {"type": "string", "description": "PO date as YYYY-MM-DD."},
            "required_by": {"type": "string", "description": "Required-by / delivery date as YYYY-MM-DD, if present."},
            "currency": {"type": "string", "description": "ISO currency code, e.g. PKR, USD, SAR."},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_name": {"type": "string"},
                        "description": {"type": "string"},
                        "qty": {"type": "number"},
                        "rate": {"type": "number", "description": "Unit price."},
                        "uom": {"type": "string", "description": "Unit of measure, e.g. Nos, Kg."},
                    },
                    "required": ["item_name", "qty"],
                },
            },
        },
        "required": ["supplier_name", "items"],
    },
}

SYSTEM_PROMPT = (
    "You are an expert purchase-order data extraction assistant. Read the attached "
    "purchase order (PDF or image) and extract the supplier, dates, currency and every "
    "line item accurately. Always use the document's own values and never invent data. "
    "Dates must be ISO format YYYY-MM-DD. Omit any field that is not present."
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _settings():
    key = None
    model = DEFAULT_MODEL
    max_tokens = 4096
    if frappe.db.exists("DocType", "VFG AI Settings"):
        s = frappe.get_single("VFG AI Settings")
        if s.get("anthropic_api_key"):
            key = s.get_password("anthropic_api_key")
        model = s.get("model") or DEFAULT_MODEL
        max_tokens = int(s.get("max_tokens") or 4096)
    if not key:
        key = frappe.conf.get("anthropic_api_key")
    if not key:
        frappe.throw("Anthropic API key is not configured. Set it in VFG AI Settings.")
    return key, model, max_tokens


def _file_block(file_url):
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    content = file_doc.get_content()
    if isinstance(content, str):
        content = content.encode("utf-8")
    b64 = base64.b64encode(content).decode("ascii")

    name = (file_doc.file_name or file_url).lower()
    if name.endswith(".pdf"):
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
    media = "image/png" if name.endswith(".png") else "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}}


# ---------------------------------------------------------------------------
# main endpoint
# ---------------------------------------------------------------------------
@frappe.whitelist()
def extract_po_document(file_url):
    api_key, model, max_tokens = _settings()

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "tools": [EXTRACT_TOOL],
        "tool_choice": {"type": "tool", "name": "extract_purchase_order"},
        "messages": [
            {
                "role": "user",
                "content": [
                    _file_block(file_url),
                    {"type": "text", "text": "Extract the purchase order details using the tool."},
                ],
            }
        ],
    }

    resp = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        data=json.dumps(payload),
        timeout=180,
    )
    if resp.status_code >= 400:
        frappe.log_error(resp.text, "AI PO extraction failed")
        frappe.throw("AI extraction failed: %s" % resp.text[:300])

    data = resp.json()
    extracted = None
    for block in data.get("content", []):
        if block.get("type") == "tool_use":
            extracted = block.get("input")
            break
    if not extracted:
        frappe.throw("AI did not return structured data. Try a clearer document.")

    return _resolve(extracted)


def _resolve(data):
    """Mark which supplier / items already exist so the UI can offer to create the rest."""
    supplier_name = (data.get("supplier_name") or "").strip()
    supplier = None
    if supplier_name:
        supplier = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
        if not supplier and frappe.db.exists("Supplier", supplier_name):
            supplier = supplier_name
    data["supplier"] = supplier
    data["supplier_exists"] = bool(supplier)

    for it in data.get("items", []):
        nm = (it.get("item_name") or "").strip()
        code = None
        if nm:
            code = frappe.db.get_value("Item", {"item_name": nm}, "name")
            if not code and frappe.db.exists("Item", nm):
                code = nm
        it["item_code"] = code
        it["item_exists"] = bool(code)
    return data


# ---------------------------------------------------------------------------
# on-the-fly creation
# ---------------------------------------------------------------------------
@frappe.whitelist()
def create_supplier(supplier_name):
    existing = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
    if existing:
        return existing
    group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
    doc = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": supplier_name,
        "supplier_group": group,
        "supplier_type": "Company",
    })
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def create_item(item_name, uom=None):
    existing = frappe.db.get_value("Item", {"item_name": item_name}, "name")
    if existing:
        return existing
    group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
    uom = uom if (uom and frappe.db.exists("UOM", uom)) else "Nos"
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_name": item_name,
        "item_group": group,
        "stock_uom": uom,
        "is_purchase_item": 1,
        "is_stock_item": 0,
    })
    doc.insert(ignore_permissions=True)
    return doc.name

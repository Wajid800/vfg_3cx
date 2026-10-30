"""Public digital-signature links for documents (Sales Invoice, Accounting
Service Agreement a.k.a. "On-Boarding").

Flow:
  1. An ERPNext user opens a Sales Invoice / Accounting Service Agreement and clicks
     "Get Signature Link" / "Generate Link".
     -> get_signature_link() creates a VFG Signature Request with a random
        token and a frozen HTML snapshot of the print format, and returns a
        public URL: https://<site>/sign?token=<token>
  2. The customer opens that URL (no login), reviews the document, draws a
     signature and submits.
     -> submit_signature() (guest) stores the signature + signer details on
        the request and attaches the signature image to the invoice.
"""

import base64
import re

import frappe
from frappe import _
from frappe.utils import now_datetime, get_url


def _clean_print_html(html):
    """Strip <script> blocks from the print snapshot. Print formats sometimes
    embed layout scripts (page-break/footer helpers) that are meant for the
    PDF renderer; inside our signing page they show up as stray text."""
    if not html:
        return ""
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"&lt;script\b.*?&lt;/script&gt;", "", html, flags=re.DOTALL | re.IGNORECASE)
    return html


# Doctypes that may get a public signing link.
SIGNABLE_DOCTYPES = ("Sales Invoice", "Accounting Service Agreement")

# Fields on the signed document to fill once the client signs
# (signature / signer name / date / "signed" checkbox).
SIGNATURE_FIELD_MAP = {
    "Accounting Service Agreement": {
        "signature": "client_signature",
        "name": "client_name",
        "date": "client_date",
        "flag": "ias",
    },
}


@frappe.whitelist()
def get_signature_link(sales_invoice, print_format=None):
    """Backwards-compatible entry point used by the Sales Invoice button."""
    return get_doc_signature_link("Sales Invoice", sales_invoice, print_format)


@frappe.whitelist()
def get_doc_signature_link(doctype, name, print_format=None):
    """Create (or reuse) a pending signature request for a document and
    return its public signing URL. Caller must be able to read the document."""
    if doctype not in SIGNABLE_DOCTYPES:
        frappe.throw(_("Signature links are not enabled for {0}").format(doctype))
    if not frappe.has_permission(doctype, "read", doc=name):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    existing = frappe.db.get_value(
        "VFG Signature Request",
        {"reference_doctype": doctype, "reference_name": name, "status": "Pending"},
        ["name", "token"],
        as_dict=True,
    )
    if existing:
        token = existing.token
    else:
        token = frappe.generate_hash(length=40)
        html = _clean_print_html(frappe.get_print(doctype, name, print_format=print_format))
        doc = frappe.new_doc("VFG Signature Request")
        doc.reference_doctype = doctype
        doc.reference_name = name
        doc.token = token
        doc.status = "Pending"
        doc.document_html = html
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

    return {"url": get_url("/sign?token=" + token), "token": token}


@frappe.whitelist(allow_guest=True)
def submit_signature(token, signature, signer_name=None):
    """Called (guest) from the public signing page to record the signature."""
    if not token or not signature:
        frappe.throw(_("Invalid request."))

    name = frappe.db.get_value("VFG Signature Request", {"token": token}, "name")
    if not name:
        frappe.throw(_("Invalid or expired link."))

    doc = frappe.get_doc("VFG Signature Request", name)
    if doc.status == "Signed":
        frappe.throw(_("This document has already been signed."))
    if doc.status == "Cancelled":
        frappe.throw(_("This link is no longer active."))

    doc.signature = signature
    doc.signer_name = (signer_name or "").strip()
    doc.signed_on = now_datetime()
    doc.signer_ip = frappe.local.request_ip
    doc.status = "Signed"
    doc.save(ignore_permissions=True)

    _attach_to_reference(doc, signature)
    _fill_signature_fields(doc, signature)
    frappe.db.commit()
    return {"ok": True}


def _fill_signature_fields(doc, signature):
    """Best-effort: copy the signature into the document's own signature
    fields. Uses db.set_value so it also works on submitted documents."""
    fmap = SIGNATURE_FIELD_MAP.get(doc.reference_doctype)
    if not fmap:
        return
    try:
        values = {fmap["signature"]: signature, fmap["date"]: frappe.utils.today(), fmap["flag"]: 1}
        if doc.signer_name:
            values[fmap["name"]] = doc.signer_name
        frappe.db.set_value(doc.reference_doctype, doc.reference_name, values)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Signature field update failed")


def _attach_to_reference(doc, signature):
    """Best-effort: save the signature PNG on the signed document + timeline note."""
    try:
        b64 = signature.split(",", 1)[1] if "," in signature else signature
        content = base64.b64decode(b64)
        frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "signature-{0}.png".format(doc.reference_name),
                "attached_to_doctype": doc.reference_doctype,
                "attached_to_name": doc.reference_name,
                "is_private": 1,
                "content": content,
            }
        ).insert(ignore_permissions=True)

        ref = frappe.get_doc(doc.reference_doctype, doc.reference_name)
        ref.add_comment(
            "Comment",
            _("Digitally signed by {0} on {1} (IP {2}).").format(
                frappe.utils.escape_html(doc.signer_name or "customer"),
                frappe.utils.format_datetime(doc.signed_on),
                doc.signer_ip or "",
            ),
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Signature attach failed")

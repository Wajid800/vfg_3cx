import re

import frappe

no_cache = 1


def _clean(html):
    """Remove <script> blocks so print-format layout scripts don't render as
    stray text on the signing page. Handles both raw (<script>) and
    HTML-escaped (&lt;script&gt;) forms, applied to old and new snapshots."""
    if not html:
        return ""
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"&lt;script\b.*?&lt;/script&gt;", "", html, flags=re.DOTALL | re.IGNORECASE)
    return html


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False

    token = frappe.form_dict.get("token")
    context.token = token or ""

    sr = None
    if token:
        name = frappe.db.get_value("VFG Signature Request", {"token": token}, "name")
        if name:
            sr = frappe.get_doc("VFG Signature Request", name)

    if not sr:
        context.state = "invalid"
        return context

    context.reference_name = sr.reference_name
    context.document_html = _clean(sr.document_html)
    context.signer_name = sr.signer_name or ""
    context.state = {
        "Signed": "signed",
        "Cancelled": "cancelled",
    }.get(sr.status, "pending")
    return context

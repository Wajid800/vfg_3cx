"""Facebook Lead Ads -> ERPNext Lead integration.

Facebook calls the webhook below whenever a Lead Ads (Instant Form) is
submitted on a connected Page. We verify the request, fetch the full lead from
the Graph API using that Page's access token, and create a Lead in ERPNext.

All credentials live in the "VFG Facebook Settings" single doctype, so the same
app code works for every install — each site just fills in its own App / Page.

Webhook callback URL (set this in Facebook App -> Webhooks):
    https://<your-erpnext-domain>/api/method/vfg_3cx.facebook.webhook
"""

import hashlib
import hmac
import json

import frappe
from werkzeug.wrappers import Response

GRAPH_API_VERSION = "v21.0"


def _settings():
    return frappe.get_single("VFG Facebook Settings")


def _verify_signature(settings, raw_body):
    """Validate Facebook's X-Hub-Signature-256 header against the App Secret.
    Returns True when valid, or when no App Secret is set (dev/testing)."""
    secret = settings.get_password("app_secret") if settings.get("app_secret") else None
    if not secret:
        return True  # not configured -> skip verification
    header = frappe.get_request_header("X-Hub-Signature-256") or ""
    if not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body or b"", hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])


@frappe.whitelist(allow_guest=True)
def webhook():
    settings = _settings()

    # --- 1) Verification handshake (Facebook sends a GET once on setup) ----
    if frappe.request.method == "GET":
        challenge = frappe.form_dict.get("hub.challenge")
        token = frappe.form_dict.get("hub.verify_token")
        if token and settings.verify_token and token == settings.verify_token:
            return Response(challenge, status=200, mimetype="text/plain")
        return Response("Verification token mismatch", status=403)

    # --- 2) Lead notifications (POST) --------------------------------------
    raw = frappe.request.get_data()
    if not _verify_signature(settings, raw):
        frappe.logger("vfg_fb").error("Facebook webhook: bad signature")
        return Response("invalid signature", status=403)

    try:
        payload = json.loads(raw or b"{}")
    except Exception:
        return Response("bad payload", status=400)

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue
            value = change.get("value") or {}
            try:
                _create_lead_from_leadgen(
                    settings,
                    leadgen_id=value.get("leadgen_id"),
                    page_id=value.get("page_id"),
                    form_id=value.get("form_id"),
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    "Facebook leadgen processing failed: %s" % value,
                )

    frappe.db.commit()
    # Always 200 so Facebook stops retrying; any errors are logged above.
    return Response("ok", status=200)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _page_token(settings, page_id):
    """Return the access token for the page that fired the webhook."""
    for row in settings.get("pages") or []:
        if str(row.page_id) == str(page_id):
            return row.get_password("page_access_token") if row.page_access_token else None
    # fallback: first configured page (single-page installs)
    if settings.get("pages"):
        row = settings.pages[0]
        return row.get_password("page_access_token") if row.page_access_token else None
    return None


def _fetch_lead(leadgen_id, token):
    import requests

    url = "https://graph.facebook.com/{v}/{id}".format(v=GRAPH_API_VERSION, id=leadgen_id)
    resp = requests.get(
        url,
        params={
            "access_token": token,
            "fields": "field_data,created_time,form_id,ad_id,ad_name,campaign_name",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _create_lead_from_leadgen(settings, leadgen_id, page_id, form_id=None):
    if not leadgen_id:
        return

    # de-dupe: skip if we already imported this exact lead
    if frappe.db.exists("Lead", {"fb_leadgen_id": leadgen_id}):
        return

    token = _page_token(settings, page_id)
    if not token:
        frappe.throw("No Page Access Token configured for page %s" % page_id)

    data = _fetch_lead(leadgen_id, token)

    # field_data -> simple {name: value} dict
    vals = {}
    for f in data.get("field_data", []):
        name = (f.get("name") or "").lower()
        values = f.get("values") or []
        vals[name] = values[0] if values else ""

    full_name = (
        vals.get("full_name")
        or (vals.get("first_name", "") + " " + vals.get("last_name", "")).strip()
        or "Facebook Lead"
    )

    lead = frappe.new_doc("Lead")
    lead.lead_name = full_name
    lead.first_name = vals.get("first_name") or full_name
    if vals.get("last_name"):
        lead.last_name = vals.get("last_name")
    lead.company_name = vals.get("company_name") or full_name
    lead.email_id = vals.get("email") or ""
    lead.mobile_no = vals.get("phone_number") or ""
    lead.fb_leadgen_id = leadgen_id

    if settings.get("lead_source"):
        lead.source = settings.lead_source
    if settings.get("lead_owner"):
        lead.lead_owner = settings.lead_owner

    lead.insert(ignore_permissions=True)

    # keep the raw answers + campaign info on the timeline for reference
    note_lines = ["Imported from Facebook Lead Ads."]
    campaign = data.get("campaign_name") or data.get("ad_name")
    if campaign:
        note_lines.append("Campaign/Ad: %s" % campaign)
    for k, v in vals.items():
        note_lines.append("%s: %s" % (k, v))  
    lead.add_comment("Comment", "<br>".join(frappe.utils.escape_html(x) for x in note_lines))

    frappe.db.commit()  
    frappe.logger("vfg_fb").info("Created Lead %s from leadgen %s" % (lead.name, leadgen_id))
    return lead.name    

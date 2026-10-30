"""3CX <-> ERPNext server-side CRM integration.

3CX calls these whitelisted endpoints when a call rings to look up the caller
in ERPNext (Contact / Lead) and show the matched record on the agent screen.

Endpoint (used in the 3CX CRM template):
    /api/method/vfg_3cx.api.get_contact_by_number?number=[Number]
"""

import frappe
from frappe.utils import get_url, get_datetime, now_datetime, add_to_date


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _digits(value):
    """Keep only the digits of a phone number."""
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _search_key(number):
    """Loose match key: last 9 digits (handles country code / formatting diff)."""
    d = _digits(number)
    return d[-9:] if len(d) > 9 else d


def _norm_sql(column):
    """SQL expression that strips spaces, dashes, brackets and + from a column."""
    return (
        "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE({c},' ',''),'-',''),'(',''),')',''),'+','')"
    ).format(c=column)


def _check_secret():
    """Optional protection. If `threecx_secret` is set in site_config.json,
    incoming requests must pass a matching ?secret=... parameter."""
    expected = frappe.conf.get("threecx_secret")
    if not expected:
        return  # not configured -> open (same as reference behaviour)
    if frappe.form_dict.get("secret") != expected:
        frappe.throw("Unauthorized", frappe.PermissionError)


# ---------------------------------------------------------------------------
# payload builders
# ---------------------------------------------------------------------------
def _contact_payload(name):
    c = frappe.get_doc("Contact", name)

    phone, mobile = c.get("phone") or "", c.get("mobile_no") or ""
    for row in (c.get("phone_nos") or []):
        if row.is_primary_mobile_no and not mobile:
            mobile = row.phone
        elif row.is_primary_phone and not phone:
            phone = row.phone
    if not phone and c.get("phone_nos"):
        phone = c.phone_nos[0].phone

    company = c.get("company_name") or ""
    if not company and c.get("links"):
        company = c.links[0].link_name or ""

    return {
        "found": True,
        "id": c.name,
        "firstname": c.first_name or "",
        "lastname": c.last_name or "",
        "company": company,
        "email": c.email_id or "",
        "phonebusiness": phone or mobile,
        "phonemobile": mobile or phone,
        "contacturl": get_url("/app/contact/" + c.name),
        "entitytype": "Contacts",
    }


def _lead_payload(name):
    l = frappe.get_doc("Lead", name)
    return {
        "found": True,
        "id": l.name,
        "firstname": l.get("first_name") or l.get("lead_name") or "",
        "lastname": l.get("last_name") or "",
        "company": l.get("company_name") or "",
        "email": l.get("email_id") or "",
        "phonebusiness": l.get("phone") or l.get("mobile_no") or "",
        "phonemobile": l.get("mobile_no") or l.get("phone") or "",
        "contacturl": get_url("/app/lead/" + l.name),
        "entitytype": "Leads",
    }


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------
def _find_by_number(key):
    if not key:
        return None
    like = "%" + key

    rows = frappe.db.sql(
        "select parent from `tabContact Phone` where {m} like %s limit 1".format(
            m=_norm_sql("phone")
        ),
        (like,),
    )
    if rows:
        return _contact_payload(rows[0][0])

    rows = frappe.db.sql(
        "select name from `tabLead` where {m} like %s or {p} like %s limit 1".format(
            m=_norm_sql("mobile_no"), p=_norm_sql("phone")
        ),
        (like, like),
    )
    if rows:
        return _lead_payload(rows[0][0])

    return None


def _find_by_email(email):
    if not email:
        return None
    rows = frappe.db.sql(
        "select parent from `tabContact Email` where email_id=%s limit 1", (email,)
    )
    if rows:
        return _contact_payload(rows[0][0])

    lead = frappe.db.get_value("Lead", {"email_id": email}, "name")
    if lead:
        return _lead_payload(lead)

    return None


# ---------------------------------------------------------------------------
# public endpoint (called by 3CX)
# ---------------------------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def get_contact_by_number(number=None, email=None, **kwargs):
    _check_secret()

    number = number or frappe.form_dict.get("number")
    email = email or frappe.form_dict.get("email")

    result = None
    key = _search_key(number)
    if key:
        result = _find_by_number(key)
    if not result and email:
        result = _find_by_email(email)

    if not result:
        frappe.logger("vfg_3cx").info(
            "3CX lookup: no match (number=%s, email=%s)" % (number, email)
        )
        return {"found": False}

    return result


# ---------------------------------------------------------------------------
# call journaling (3CX ReportCall -> VFG 3CX Call Log)
# ---------------------------------------------------------------------------
def _parse_duration(value):
    """3CX sends duration as 'hh:mm:ss' (or seconds). Return total seconds."""
    if not value:
        return 0
    value = str(value).strip()
    if ":" in value:
        parts = [int(p or 0) for p in value.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, s = parts[-3], parts[-2], parts[-1]
        return h * 3600 + m * 60 + s
    try:
        return int(float(value))
    except ValueError:
        return 0


def _parse_dt(value):
    if value:
        try:
            return get_datetime(value)
        except Exception:
            pass
    return now_datetime()


@frappe.whitelist(allow_guest=True)
def log_call(**kwargs):
    """Called by 3CX at the end of a call to record it in VFG 3CX Call Log."""
    _check_secret()
    d = frappe.form_dict

    number = d.get("number")
    agent = d.get("agent")
    call_type = (d.get("call_type") or "").strip()
    duration = _parse_duration(d.get("duration"))
    when = _parse_dt(d.get("datetime"))
    entity_id = d.get("entity_id")
    entity_type = (d.get("entity_type") or "").strip()

    direction = "Outbound" if call_type in ("Outbound", "Notanswered") else "Inbound"
    status = {
        "Inbound": "Answered",
        "Outbound": "Answered",
        "Missed": "Missed",
        "Notanswered": "Failed",
    }.get(call_type, "Completed")

    if direction == "Inbound":
        from_number, to_number = number, agent
    else:
        from_number, to_number = agent, number

    doc = frappe.new_doc("VFG 3CX Call Log")
    doc.direction = direction
    doc.status = status
    doc.from_number = from_number
    doc.to_number = to_number
    doc.extension = agent
    doc.start_time = when
    doc.duration = duration

    if entity_id and entity_type == "Contacts" and frappe.db.exists("Contact", entity_id):
        doc.contact = entity_id
    elif entity_id and entity_type == "Leads" and frappe.db.exists("Lead", entity_id):
        doc.lead = entity_id

    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "name": doc.name}


# ---------------------------------------------------------------------------
# click-to-call (ERPNext -> 3CX Call Control API)
#
# Lets agents place outbound calls straight from a Lead / Contact / Customer
# form without ever opening the 3CX panel. The call originates from the
# logged-in user's own 3CX extension; the resulting call is journaled back
# into VFG 3CX Call Log by the existing ReportCall scenarios.
# ---------------------------------------------------------------------------
def _settings():
    s = frappe.get_single("VFG 3CX Settings")
    if not s.enabled:
        frappe.throw("3CX integration is disabled. Enable it in VFG 3CX Settings.")
    if not s.server_url:
        frappe.throw("3CX Server URL is not configured in VFG 3CX Settings.")
    return s


def _get_access_token(settings):
    """Return a valid Call Control API token, refreshing via the OAuth
    client-credentials grant when the cached one is missing or expired."""
    import requests

    token = settings.get("access_token")
    expires_at = settings.get("token_expires_at")
    if token and expires_at and get_datetime(expires_at) > now_datetime():
        return token

    client_id = settings.get("api_client_id")
    client_secret = settings.get_password("api_client_secret") if settings.get("api_client_secret") else None
    if not client_id or not client_secret:
        frappe.throw("Call Control API Client ID / Secret are not configured in VFG 3CX Settings.")

    base = settings.server_url.rstrip("/")
    try:
        resp = requests.post(
            base + "/connect/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "3CX token request failed")
        frappe.throw("Could not authenticate with 3CX: %s" % e)

    data = resp.json()
    token = data.get("access_token")
    if not token:
        frappe.throw("3CX did not return an access token.")

    # refresh a minute early to avoid edge-of-expiry races
    expires_in = int(data.get("expires_in") or 3600)
    settings.access_token = token
    settings.token_expires_at = add_to_date(now_datetime(), seconds=max(expires_in - 60, 60))
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    return token


def _extension_for_user(settings, user):
    """Resolve the 3CX extension for an ERPNext user: explicit mapping first,
    then the single default extension from settings."""
    for row in settings.get("agent_extensions") or []:
        if row.user == user and row.extension:
            return row.extension.strip()
    if settings.get("extension"):
        return settings.extension.strip()
    return None


def _registered_device_id(base, token, extension):
    """Return a registered device id for the extension.

    makecall placed at the DN level (/callcontrol/{dn}/makecall) often connects
    but yields no audio, because it is not bound to the agent's actual endpoint.
    Placing it from the specific registered device fixes the media path.
    """
    import requests

    try:
        resp = requests.get(
            "{base}/callcontrol/{dn}".format(base=base, dn=extension),
            headers={"Authorization": "Bearer " + token},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    devices = data.get("devices") if isinstance(data, dict) else None
    for d in devices or []:
        if d.get("device_id"):
            return d["device_id"]
    return None


@frappe.whitelist()
def make_call(number, reference_doctype=None, reference_name=None):
    """Place an outbound call from the current user's 3CX extension to `number`.

    Called from the desk forms (Lead / Contact / Customer). Authentication is
    the standard logged-in session, so only ERPNext users can trigger calls.
    """
    import requests
    from urllib.parse import quote

    number = (number or "").strip()
    if not number:
        frappe.throw("No phone number to call.")

    settings = _settings()

    user = frappe.session.user
    extension = _extension_for_user(settings, user)
    if not extension:
        frappe.throw(
            "No 3CX extension is mapped to your user ({0}). "
            "Ask an administrator to add it under VFG 3CX Settings → Agent Extensions.".format(user)
        )

    token = _get_access_token(settings)
    base = settings.server_url.rstrip("/")

    def _makecall(tok):
        # prefer the registered device (reliable two-way audio); fall back to
        # the plain DN-level endpoint if no device can be resolved.
        device_id = _registered_device_id(base, tok, extension)
        if device_id:
            url = "{base}/callcontrol/{dn}/devices/{dev}/makecall".format(
                base=base, dn=extension, dev=quote(str(device_id), safe="")
            )
        else:
            url = "{base}/callcontrol/{dn}/makecall".format(base=base, dn=extension)
        return url, requests.post(
            url,
            json={"destination": number},
            headers={
                "Authorization": "Bearer " + tok,
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=15,
        )

    try:
        url, resp = _makecall(token)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "3CX makecall failed")
        frappe.throw("Could not reach 3CX to place the call: %s" % e)

    # token may have been revoked server-side; retry once with a fresh one
    if resp.status_code in (401, 403):
        settings.access_token = None
        settings.token_expires_at = None
        token = _get_access_token(settings)
        url, resp = _makecall(token)

    if resp.status_code not in (200, 202):
        frappe.log_error(
            "POST %s -> %s\n%s" % (url, resp.status_code, resp.text),
            "3CX makecall rejected",
        )
        frappe.throw(
            "3CX rejected the call (HTTP {0}). Check that extension {1} is registered "
            "and the API client can control it.".format(resp.status_code, extension)
        )

    frappe.logger("vfg_3cx").info(
        "click-to-call: %s (ext %s) -> %s [%s %s]"
        % (user, extension, number, reference_doctype or "", reference_name or "")
    )

    return {
        "ok": True,
        "extension": extension,
        "number": number,
    }

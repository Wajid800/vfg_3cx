"""Fill the official I-9 PDF from an Employee I9 Verification record.

Uses the field map in vfg_3cx.i9_field_map and the bundled template
vfg_3cx/pdf_templates/i9.pdf. Produces a completed PDF and attaches it to the
record's `filled_pdf` field.
"""

import io
import json
import re

import frappe
from frappe.utils import getdate, get_url, today

from vfg_3cx.i9_field_map import (
    I9_TEXT_MAP,
    I9_STATE_FIELD,
    I9_EMPLOYEE_SIGNATURE_FIELD,
    I9_EMPLOYER_SIGNATURE_FIELD,
    I9_CITIZENSHIP_CHECKBOX,
    I9_USCIS_A_NUMBER_LPR,
    I9_USCIS_A_NUMBER_ALIEN,
    I9_ALT_PROCEDURE_CHECKBOX,
    I9_DOCUMENT_FIELDS,
)

CHECKBOX_ON = "/On"          # CB_1..CB_4 checked value
ALT_CHECKBOX_ON = "/Yes"     # CB_Alt checked value

_DATE_FIELDS = {
    "date_of_birth",
    "work_authorized_until",
    "employee_signature_date",
    "first_day_of_employment",
    "employer_signature_date",
}


def _mmddyyyy(value):
    if not value:
        return ""
    return getdate(value).strftime("%m/%d/%Y")


def _template_path():
    return frappe.get_app_path("vfg_3cx", "pdf_templates", "i9.pdf")


def autofill_i9_dates(doc, method=None):
    """Set a signature's 'Signed On' date to today when the signature exists
    but the date is blank. Wired to before_save / before_update_after_submit."""
    if doc.get("employee_signature") and not doc.get("employee_signature_date"):
        doc.employee_signature_date = today()
    if doc.get("employer_signature") and not doc.get("employer_signature_date"):
        doc.employer_signature_date = today()


def _build_field_values(doc):
    """Translate an Employee I9 Verification doc into {pdf_field: value}."""
    v = {}

    # simple text fields
    for erp_field, pdf_field in I9_TEXT_MAP.items():
        val = doc.get(erp_field)
        if erp_field in _DATE_FIELDS:
            val = _mmddyyyy(val)
        elif erp_field == "ssn" and val:
            val = re.sub(r"\D", "", str(val))  # I-9 SSN field holds 9 digits, no dashes
        if val:
            v[pdf_field] = str(val)

    # state is an AcroForm choice (two-letter code)
    if doc.get("state"):
        v[I9_STATE_FIELD] = str(doc.state).strip().upper()[:2]

    # signatures rendered as the typed name (image is kept in ERPNext)
    emp_name = " ".join(x for x in [doc.get("employee_first_name"), doc.get("employee_last_name")] if x)
    if emp_name:
        v[I9_EMPLOYEE_SIGNATURE_FIELD] = emp_name
    if doc.get("employer_representative_name_title"):
        v[I9_EMPLOYER_SIGNATURE_FIELD] = doc.employer_representative_name_title

    # citizenship checkbox (exactly one)
    cb = I9_CITIZENSHIP_CHECKBOX.get(doc.get("citizenship_status"))
    if cb:
        v[cb] = CHECKBOX_ON

    # USCIS A-Number goes to the field matching the chosen status
    if doc.get("uscis_a_number"):
        if doc.get("citizenship_status") == "A lawful permanent resident":
            v[I9_USCIS_A_NUMBER_LPR] = doc.uscis_a_number
        else:
            v[I9_USCIS_A_NUMBER_ALIEN] = doc.uscis_a_number

    # alternative DHS procedure checkbox
    if doc.get("alternative_procedure_used"):
        v[I9_ALT_PROCEDURE_CHECKBOX] = ALT_CHECKBOX_ON

    # List A / B / C documents
    for row in doc.get("documents") or []:
        mapping = I9_DOCUMENT_FIELDS.get((row.document_list, int(row.document_order or 1)))
        if not mapping:
            continue
        if mapping.get("title") and row.document_title:
            v[mapping["title"]] = row.document_title
        if mapping.get("authority") and row.issuing_authority:
            v[mapping["authority"]] = row.issuing_authority
        if mapping.get("number") and row.document_number:
            v[mapping["number"]] = row.document_number
        if mapping.get("expiration") and row.expiration_date:
            v[mapping["expiration"]] = _mmddyyyy(row.expiration_date)

    return v


_HEX_TJ = re.compile(rb"<([0-9A-Fa-f]{2,})>\s*Tj")


def _pdf_escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _fix_appearance_encoding(writer):
    """Older pypdf (e.g. 3.17.x, shipped with Frappe) writes filled-field
    appearance text as UTF-16BE hex `<0077..>` while the field font is
    single-byte, so viewers render a stray glyph before every character
    (e.g. "&w&a&j&i&d"). Rewrite those hex strings back to plain `(text)`."""

    def repl(m):
        try:
            raw = bytes.fromhex(m.group(1).decode())
        except Exception:
            return m.group(0)
        # only touch UTF-16BE-looking strings (even length, leading 0x00)
        if len(raw) % 2 or raw[0:1] != b"\x00":
            return m.group(0)
        text = raw.decode("utf-16-be", "replace")
        return ("(" + _pdf_escape(text) + ") Tj").encode("latin-1", "replace")

    def walk(fields):
        for ref in fields:
            obj = ref.get_object()
            ap = obj.get("/AP")
            if ap and ap.get_object().get("/N"):
                stream = ap.get_object().get("/N").get_object()
                try:
                    data = stream.get_data()
                except Exception:
                    data = None
                if data:
                    new = _HEX_TJ.sub(repl, data)
                    if new != data:
                        stream.set_data(new)
            if "/Kids" in obj:
                walk(obj["/Kids"])

    acro = writer._root_object.get("/AcroForm")
    if acro:
        walk(acro.get_object().get("/Fields") or [])


def _ensure_dr_fonts(writer):
    """Make sure the standard fonts referenced by generated appearances exist
    in the AcroForm default resources, so every viewer can render them."""
    from pypdf.generic import DictionaryObject, NameObject

    acro = writer._root_object.get("/AcroForm")
    if not acro:
        return
    dr = (acro.get_object().get("/DR") or {})
    dr = dr.get_object() if dr else None
    if dr is None:
        return
    fonts = dr.get("/Font")
    if fonts is None:
        return
    fonts = fonts.get_object()
    for fname, base in (("/Helv", "/Helvetica"), ("/Helvetica", "/Helvetica"),
                        ("/Helvetica-Bold", "/Helvetica-Bold")):
        if fname not in fonts:
            fonts[NameObject(fname)] = DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject(base),
            })


def _fill_pdf(template_path, field_values, image_overlays=None):
    """Fill the AcroForm, bake in appearance streams, and repair the text
    encoding so values are visible in every viewer (browsers included),
    regardless of the installed pypdf version.

    image_overlays: {pdf_field_name: data_url} — hand-drawn signature images
    stamped onto those fields' positions (on top of the flattened content)."""
    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=template_path)
    _ensure_dr_fonts(writer)
    for page in writer.pages:
        writer.update_page_form_field_values(page, field_values, auto_regenerate=False)
    _fix_appearance_encoding(writer)

    # capture signature field positions before the form is removed
    sig_targets = _collect_field_rects(writer, image_overlays) if image_overlays else {}

    # make the result non-editable: flatten the form (bake field appearances
    # into the page), falling back to read-only locking if that fails.
    try:
        _flatten(writer)
    except Exception:
        _lock_fields(writer)

    # stamp the drawn signatures on top of the flattened page
    for fname, (page, rect) in sig_targets.items():
        try:
            _stamp_image(writer, page, rect, image_overlays[fname])
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Signature stamp failed: %s" % fname)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _collect_field_rects(writer, field_names):
    """Return {field_name: (page, rect)} for the given AcroForm fields."""
    out = {}
    for page in writer.pages:
        annots = page.get("/Annots")
        if not annots:
            continue
        for ref in annots.get_object():
            obj = ref.get_object()
            name = obj.get("/T")
            if name in field_names and field_names.get(name) and "/Rect" in obj:
                out[name] = (page, [float(x) for x in obj["/Rect"]])
    return out


def _stamp_image(writer, page, rect, data_url):
    """Draw a PNG data-URL image (a signature) onto `page` sitting on the
    field's baseline, scaled to fit the field width (max ~22pt tall)."""
    import base64
    import io as _io
    from PIL import Image
    from pypdf.generic import (
        NameObject,
        DictionaryObject,
        NumberObject,
        StreamObject,
        DecodedStreamObject,
        ArrayObject,
    )

    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
    img = Image.open(_io.BytesIO(base64.b64decode(b64)))
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, "white")
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")
    iw, ih = img.size
    jpg_buf = _io.BytesIO()
    img.save(jpg_buf, format="JPEG", quality=85)
    jpg = jpg_buf.getvalue()

    x0, y0 = min(rect[0], rect[2]), min(rect[1], rect[3])
    rw = max(rect[0], rect[2]) - x0
    # fit to field width, cap height so it doesn't cover the line above
    dw = rw
    dh = dw * ih / iw
    max_h = 24.0
    if dh > max_h:
        dh = max_h
        dw = dh * iw / ih 
    dx = x0
    dy = y0  # sit on the baseline, extend upward

    xobj = StreamObject()
    xobj[NameObject("/Type")] = NameObject("/XObject")
    xobj[NameObject("/Subtype")] = NameObject("/Image")
    xobj[NameObject("/Width")] = NumberObject(iw)
    xobj[NameObject("/Height")] = NumberObject(ih)
    xobj[NameObject("/ColorSpace")] = NameObject("/DeviceRGB")
    xobj[NameObject("/BitsPerComponent")] = NumberObject(8)
    xobj[NameObject("/Filter")] = NameObject("/DCTDecode")
    xobj[NameObject("/Length")] = NumberObject(len(jpg))
    xobj._data = jpg
    img_ref = writer._add_object(xobj)

    if "/Resources" not in page:
        page[NameObject("/Resources")] = DictionaryObject()
    res = page["/Resources"].get_object()
    if "/XObject" not in res:
        res[NameObject("/XObject")] = DictionaryObject()
    xobjects = res["/XObject"].get_object()
    name = "/Sig%d" % len(xobjects)
    xobjects[NameObject(name)] = img_ref

    ops = "\nq %.4f 0 0 %.4f %.4f %.4f cm %s Do Q\n" % (dw, dh, dx, dy, name)
    cs = DecodedStreamObject()
    cs.set_data(ops.encode("latin-1"))
    cs_ref = writer._add_object(cs)
    contents = page.get("/Contents")
    if contents is None:
        page[NameObject("/Contents")] = cs_ref
    elif isinstance(contents.get_object(), ArrayObject):
        contents.get_object().append(cs_ref)
    else:
        page[NameObject("/Contents")] = ArrayObject([contents, cs_ref])


def _flatten(writer):
    """Draw every field's appearance directly onto the page content and remove
    the interactive form, so no field can be clicked or edited in any viewer."""
    from pypdf.generic import (
        NameObject,
        DictionaryObject,
        ArrayObject,
        DecodedStreamObject,
    )

    for page in writer.pages:
        annots = page.get("/Annots")
        if not annots:
            continue

        if "/Resources" not in page:
            page[NameObject("/Resources")] = DictionaryObject()
        resources = page["/Resources"].get_object()
        if "/XObject" not in resources:
            resources[NameObject("/XObject")] = DictionaryObject()
        xobjects = resources["/XObject"].get_object()

        ops = ""
        idx = 0
        for ref in annots.get_object():
            obj = ref.get_object()
            ap = obj.get("/AP")
            if not ap:
                continue
            normal = ap.get_object().get("/N")
            if normal is None:
                continue
            normal = normal.get_object()

            # checkboxes/radios: /N is keyed by state; pick the current /AS
            if "/BBox" not in normal and hasattr(normal, "get"):
                state = obj.get("/AS")
                stream = normal.get(state)
                stream = stream.get_object() if stream is not None else None
            else:
                stream = normal
            if stream is None or not hasattr(stream, "get_data"):
                continue

            rect = [float(x) for x in obj["/Rect"]]
            x0, y0 = min(rect[0], rect[2]), min(rect[1], rect[3])
            x1, y1 = max(rect[0], rect[2]), max(rect[1], rect[3])
            rw, rh = (x1 - x0) or 1, (y1 - y0) or 1
            bbox = [float(b) for b in (stream.get("/BBox") or [0, 0, rw, rh])]
            bw = (bbox[2] - bbox[0]) or 1
            bh = (bbox[3] - bbox[1]) or 1
            sx, sy = rw / bw, rh / bh

            name = "/Fl%d" % idx
            idx += 1
            xobjects[NameObject(name)] = writer._add_object(stream)
            ops += "q %.4f 0 0 %.4f %.4f %.4f cm %s Do Q\n" % (
                sx, sy, x0 - bbox[0] * sx, y0 - bbox[1] * sy, name
            )

        if ops:
            cs = DecodedStreamObject()
            cs.set_data(("\nq\n" + ops + "Q\n").encode("latin-1", "replace"))
            new_ref = writer._add_object(cs)
            contents = page.get("/Contents")   
            if contents is None:
                page[NameObject("/Contents")] = new_ref
            elif isinstance(contents.get_object(), ArrayObject):
                contents.get_object().append(new_ref)
            else:
                page[NameObject("/Contents")] = ArrayObject([contents, new_ref])

        del page[NameObject("/Annots")]

    if "/AcroForm" in writer._root_object:
        del writer._root_object[NameObject("/AcroForm")]


def _lock_fields(writer):
    """Mark every form field read-only so the generated PDF cannot be edited
    (clicked and typed into), while keeping the filled values visible. We set
    the flag on the actual page widgets (what viewers use) and their parents."""
    from pypdf.generic import NameObject, NumberObject

    READ_ONLY = 1  # bit 1 of field flags

    def set_ro(obj):
        ff = int(obj.get("/Ff") or 0)
        obj[NameObject("/Ff")] = NumberObject(ff | READ_ONLY)

    for page in writer.pages:
        annots = page.get("/Annots")
        if not annots:
            continue
        for ref in annots.get_object():
            obj = ref.get_object()
            if obj.get("/Subtype") == "/Widget" or obj.get("/FT"):
                set_ro(obj)
                parent = obj.get("/Parent")
                if parent:
                    set_ro(parent.get_object())


@frappe.whitelist()
def generate_i9_pdf(name):
    """Generate the filled I-9 PDF and attach it to the record."""
    doc = frappe.get_doc("Employee I9 Verification", name)
    doc.check_permission("read")

    overlays = {}
    if doc.employee_signature:
        overlays[I9_EMPLOYEE_SIGNATURE_FIELD] = doc.employee_signature
    if doc.employer_signature:
        overlays[I9_EMPLOYER_SIGNATURE_FIELD] = doc.employer_signature

    content = _fill_pdf(_template_path(), _build_field_values(doc), image_overlays=overlays)

    filename = "I-9_{0}.pdf".format((doc.employee_last_name or doc.name).replace(" ", "_"))
    _file = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "attached_to_doctype": "Employee I9 Verification",
            "attached_to_name": doc.name,
            "attached_to_field": "filled_pdf",
            "is_private": 1,
            "content": content,
        }
    ).insert(ignore_permissions=True)

    doc.db_set("filled_pdf", _file.file_url)
    return {"file_url": _file.file_url}


# ---------------------------------------------------------------------------
# employee self-service (public link for Section 1)
# ---------------------------------------------------------------------------
# Fields the employee may fill/overwrite via the public page. Section 2
# (employer) fields and status are never writable from the guest endpoint.
SECTION1_FIELDS = [
    "employee_first_name",
    "employee_middle_initial",
    "employee_last_name",
    "other_last_names_used",
    "address_line1",
    "apartment_number",
    "city",
    "state",
    "zip_code",
    "date_of_birth",
    "ssn",
    "personal_email",
    "cell_number",
    "citizenship_status",
    "uscis_a_number",
    "i94_admission_number",
    "work_authorized_until",
    "foreign_passport_number",
    "passport_country_of_issuance",
]


@frappe.whitelist()
def get_i9_link(name):
    """Create/return a public link for the employee to complete Section 1."""
    if not frappe.has_permission("Employee I9 Verification", "write", doc=name):
        frappe.throw("Not permitted", frappe.PermissionError)

    doc = frappe.get_doc("Employee I9 Verification", name)
    already_signed = doc.status in ("Employee Signed", "Completed")
    if not doc.token:
        doc.token = frappe.generate_hash(length=40)
    if doc.status in (None, "", "Draft"):
        doc.status = "Sent to Employee"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {
        "url": get_url("/i9?token=" + doc.token),
        "token": doc.token,
        "already_signed": already_signed,
    }


@frappe.whitelist(allow_guest=True)
def submit_i9_section1(token, data, signature=None):
    """Guest endpoint: save the employee's Section 1 answers + signature."""
    if not token:
        frappe.throw("Invalid request.")

    name = frappe.db.get_value("Employee I9 Verification", {"token": token}, "name")
    if not name:
        frappe.throw("Invalid or expired link.")

    doc = frappe.get_doc("Employee I9 Verification", name)
    if doc.status == "Completed":
        frappe.throw("This form has already been completed.")

    payload = json.loads(data or "{}")
    for f in SECTION1_FIELDS:
        if f in payload:
            doc.set(f, payload.get(f) or None)

    if signature:
        doc.employee_signature = signature
        doc.employee_signature_date = today()

    doc.status = "Employee Signed"
    doc.flags.ignore_permissions = True
    if doc.docstatus == 0 and frappe.get_meta(doc.doctype).is_submittable:
        doc.submit()  # finalize (docstatus=1) when the employee submits
    else:
        doc.save()
    frappe.db.commit()
    return {"ok": True}


# ===========================================================================
# W-4 (Employee's Withholding Certificate)
# ===========================================================================
_W4_MONEY_FIELDS = {
    "step3_qualifying_children",
    "step3_other_dependents",
    "step3_total",
    "step4a_other_income",
    "step4b_deductions",
    "step4c_extra_withholding",
}

W4_SECTION1_FIELDS = [
    "first_name_mi",
    "last_name",
    "ssn",
    "address",
    "city_state_zip",
    "filing_status",
    "multiple_jobs",
    "step3_qualifying_children",
    "step3_other_dependents",
    "step3_total",
    "step4a_other_income",
    "step4b_deductions",
    "step4c_extra_withholding",
]


def _w4_template_path():
    return frappe.get_app_path("vfg_3cx", "pdf_templates", "w4.pdf")


def _num(val):
    try:
        f = float(val)
        return str(int(f)) if f == int(f) else ("%.2f" % f)
    except Exception:
        return str(val)


def _build_w4_field_values(doc):
    from vfg_3cx.w4_field_map import (
        W4_TEXT_MAP,
        W4_FIRST_DATE_FIELD,
        W4_FILING_STATUS,
        W4_FILING_WIDGETS,
        W4_MULTIPLE_JOBS_FIELD,
        W4_MULTIPLE_JOBS_ON,
    )

    v = {}
    for erp_field, pdf_field in W4_TEXT_MAP.items():
        val = doc.get(erp_field)
        if erp_field == "ssn" and val:
            val = re.sub(r"\D", "", str(val))
        elif erp_field in _W4_MONEY_FIELDS and val:
            val = _num(val)
        if val not in (None, "", 0, 0.0):
            v[pdf_field] = str(val)

    if doc.get("first_date_of_employment"):
        v[W4_FIRST_DATE_FIELD] = _mmddyyyy(doc.first_date_of_employment)

    # filing status radio: clear all, then set the selected option
    for widget in W4_FILING_WIDGETS:
        v[widget] = "/Off"
    if doc.get("filing_status") in W4_FILING_STATUS:
        widget, on = W4_FILING_STATUS[doc.filing_status]
        v[widget] = on

    if doc.get("multiple_jobs"):
        v[W4_MULTIPLE_JOBS_FIELD] = W4_MULTIPLE_JOBS_ON

    return v


@frappe.whitelist()
def generate_w4_pdf(name):
    """Generate the filled W-4 PDF and attach it to the record."""
    doc = frappe.get_doc("Employee W4", name)
    doc.check_permission("read")

    content = _fill_pdf(_w4_template_path(), _build_w4_field_values(doc))

    filename = "W-4_{0}.pdf".format((doc.last_name or doc.name).replace(" ", "_"))
    _file = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "attached_to_doctype": "Employee W4",
            "attached_to_name": doc.name,
            "attached_to_field": "filled_pdf",
            "is_private": 1,
            "content": content,
        }
    ).insert(ignore_permissions=True)

    doc.db_set("filled_pdf", _file.file_url)
    return {"file_url": _file.file_url}


@frappe.whitelist()
def get_w4_link(name):
    if not frappe.has_permission("Employee W4", "write", doc=name):
        frappe.throw("Not permitted", frappe.PermissionError)

    doc = frappe.get_doc("Employee W4", name)
    already_signed = doc.status in ("Employee Signed", "Completed")
    if not doc.token:
        doc.token = frappe.generate_hash(length=40)
    if doc.status in (None, "", "Draft"):
        doc.status = "Sent to Employee"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {
        "url": get_url("/w4?token=" + doc.token),
        "token": doc.token,
        "already_signed": already_signed,
    }


@frappe.whitelist(allow_guest=True)
def submit_w4(token, data, signature=None):
    if not token:
        frappe.throw("Invalid request.")

    name = frappe.db.get_value("Employee W4", {"token": token}, "name")
    if not name:
        frappe.throw("Invalid or expired link.")

    doc = frappe.get_doc("Employee W4", name)
    if doc.status == "Completed":
        frappe.throw("This form has already been completed.")

    payload = json.loads(data or "{}")
    for f in W4_SECTION1_FIELDS:
        if f in payload:
            doc.set(f, payload.get(f) or None)

    if signature:
        doc.employee_signature = signature
        doc.employee_signature_date = today()

    doc.status = "Employee Signed"
    doc.flags.ignore_permissions = True
    if doc.docstatus == 0 and frappe.get_meta(doc.doctype).is_submittable:
        doc.submit()  # finalize (docstatus=1) when the employee submits
    else:
        doc.save()
    frappe.db.commit()
    return {"ok": True}

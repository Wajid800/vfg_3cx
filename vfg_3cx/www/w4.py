import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False

    token = frappe.form_dict.get("token")
    context.token = token or ""

    doc = None
    if token:
        name = frappe.db.get_value("Employee W4", {"token": token}, "name")
        if name:
            doc = frappe.get_doc("Employee W4", name)

    if not doc:
        context.state = "invalid"
        return context

    context.state = "signed" if doc.status in ("Employee Signed", "Completed") else "open"
    context.d = doc
    return context

// AI Auto-Fill for Purchase Order.
// Adds a button that uploads a PO document (PDF/image), sends it to Claude AI
// via vfg_3cx.ai_po, and fills the form — creating supplier/items if missing.

frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		frm.add_custom_button(__("AI Auto-Fill from Document"), () => {
			new frappe.ui.FileUploader({
				allow_multiple: false,
				restrictions: {
					allowed_file_types: [".pdf", ".png", ".jpg", ".jpeg"],
				},
				on_success(file_doc) {
					vfg_extract_po(frm, file_doc.file_url);
				},
			});
		});
	},
});

function vfg_extract_po(frm, file_url) {
	frappe.dom.freeze(__("Reading document with AI…"));
	frappe.call({
		method: "vfg_3cx.ai_po.extract_po_document",
		args: { file_url },
		callback(r) {
			frappe.dom.unfreeze();
			if (r.message) {
				vfg_apply_po(frm, r.message);
			}
		},
		error() {
			frappe.dom.unfreeze();
		},
	});
}

function vfg_confirm(message) {
	return new Promise((resolve) => {
		frappe.confirm(
			message,
			() => resolve(true),
			() => resolve(false),
		);
	});
}

async function vfg_apply_po(frm, data) {
	// 1) Supplier ---------------------------------------------------------
	let supplier = data.supplier;
	if (!supplier && data.supplier_name) {
		const ok = await vfg_confirm(
			__('Supplier "{0}" does not exist. Create it?', [data.supplier_name]),
		);
		if (ok) {
			const res = await frappe.call({
				method: "vfg_3cx.ai_po.create_supplier",
				args: { supplier_name: data.supplier_name },
			});
			supplier = res.message;
		}
	}
	if (supplier) {
		await frm.set_value("supplier", supplier);
	}

	// 2) Header fields ----------------------------------------------------
	if (data.transaction_date) await frm.set_value("transaction_date", data.transaction_date);
	if (data.currency) await frm.set_value("currency", data.currency);

	// 3) Create missing items --------------------------------------------
	const missing = (data.items || []).filter((it) => !it.item_code && it.item_name);
	if (missing.length) {
		const names = missing.map((it) => it.item_name).join(", ");
		const ok = await vfg_confirm(__("These items do not exist: {0}. Create them?", [names]));
		if (ok) {
			for (const it of missing) {
				const res = await frappe.call({
					method: "vfg_3cx.ai_po.create_item",
					args: { item_name: it.item_name, uom: it.uom || null },
				});
				it.item_code = res.message;
			}
		}
	}

	// 4) Fill the items table --------------------------------------------
	const default_schedule =
		data.required_by || frappe.datetime.add_days(frappe.datetime.nowdate(), 7);
	frm.clear_table("items");
	for (const it of data.items || []) {
		if (!it.item_code) continue; // skip items the user chose not to create
		const row = frm.add_child("items");
		row.item_code = it.item_code;
		row.qty = it.qty || 1;
		if (it.rate) row.rate = it.rate;
		if (it.description) row.description = it.description;
		if (it.uom) row.uom = it.uom;
		row.schedule_date = default_schedule;
	}
	frm.refresh_field("items");

	frappe.show_alert(
		{
			message: __("PO auto-filled from document. Please review and Save."),
			indicator: "green",
		},
		7,
	);
}

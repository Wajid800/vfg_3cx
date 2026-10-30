// Click-to-call for 3CX (tel: deep-link method).
//
// Adds a "📞 Call" button to CRM forms. Clicking it opens a tel: link so the
// number lands directly in the agent's 3CX dialer (agent then presses the
// green call button). No picker popup — one click loads the primary number.

// Normalise a number for dialling: keep a leading "+", drop everything else
// that isn't a digit (spaces, dashes, brackets).
function vfg_3cx_clean(number) {
	number = (number || "").trim();
	const plus = number.startsWith("+") ? "+" : "";
	return plus + number.replace(/[^0-9]/g, "");
}

function vfg_3cx_place_call(frm, number) {
	const clean = vfg_3cx_clean(number);
	if (!clean) {
		frappe.msgprint({
			title: __("No Number"),
			message: __("This record has no valid phone/mobile number to call."),
			indicator: "orange",
		});
		return;
	}

	// Hand the number to the 3CX dialer via the tel: protocol handler.
	const a = document.createElement("a");
	a.href = "tel:" + clean;
	a.style.display = "none";
	document.body.appendChild(a);
	a.click();
	a.remove();

	frappe.show_alert(
		{ message: __("Opening {0} in 3CX dialer…", [clean]), indicator: "blue" },
		5,
	);
}

// Build the Call button. `fields` is an ordered list of [label, fieldname]
// pairs; the first non-empty one is the default to dial.
function vfg_3cx_add_call_button(frm, fields) {
	const numbers = fields
		.map(([label, fieldname]) => [label, (frm.doc[fieldname] || "").trim()])
		.filter(([, value]) => value);

	if (!numbers.length) {
		return; // nothing to call on this record
	}

	// Call the primary number directly (first non-empty: Mobile > Phone > …).
	// No picker dialog — one click places the call.
	frm.add_custom_button(__("📞 Call"), () => {
		vfg_3cx_place_call(frm, numbers[0][1]);
	});
}

frappe.ui.form.on("Lead", {
	refresh(frm) {
		if (frm.is_new()) return;
		vfg_3cx_add_call_button(frm, [
			[__("Mobile"), "mobile_no"],
			[__("Phone"), "phone"],
			[__("WhatsApp"), "whatsapp"],
		]);
	},
});

frappe.ui.form.on("Contact", {
	refresh(frm) {
		if (frm.is_new()) return;
		vfg_3cx_add_call_button(frm, [
			[__("Mobile"), "mobile_no"],
			[__("Phone"), "phone"],
		]);
	},
});

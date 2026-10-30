// Adds a button to generate the filled official I-9 PDF from the record's data
// and attach it (vfg_3cx.onboarding.generate_i9_pdf).

frappe.ui.form.on("Employee I9 Verification", {
	refresh(frm) {
		if (frm.is_new()) return;

		// Public self-service link for the employee to fill Section 1.
		frm.add_custom_button(__("Get Employee Link"), () => {
			frappe.call({
				method: "vfg_3cx.onboarding.get_i9_link",
				args: { name: frm.doc.name },
				freeze: true,
				callback(r) {
					if (!r.message || !r.message.url) return;
					frm.reload_doc();
					if (r.message.already_signed) {
						frappe.msgprint({
							title: __("Already Signed"),
							indicator: "green",
							message: __("This employee has already filled and signed the I-9 form."),
						});
						return;
					}
					const safe = frappe.utils.escape_html(r.message.url);
					frappe.msgprint({
						title: __("Employee I-9 Link"),
						indicator: "blue",
						message: `
							<p>${__("Send this link to the employee. They fill Section 1 and sign — no login needed.")}</p>
							<input id="i9-url" class="form-control" value="${safe}" readonly onclick="this.select()" style="margin-bottom:8px;">
							<button class="btn btn-sm btn-primary"
								onclick="navigator.clipboard.writeText(document.getElementById('i9-url').value).then(function(){frappe.show_alert({message:__('Link copied'),indicator:'green'});})">
								${__("Copy link")}
							</button>
							<a href="${safe}" target="_blank" class="btn btn-sm btn-default">${__("Open link")}</a>`,
					});
				},
			});
		});

		frm.add_custom_button(__("Generate Filled I-9 PDF"), () => {
			frappe.call({
				method: "vfg_3cx.onboarding.generate_i9_pdf",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Filling the official I-9 form…"),
				callback(r) {
					if (r.message && r.message.file_url) {
						frm.reload_doc();
						frappe.show_alert(
							{ message: __("I-9 PDF generated."), indicator: "green" },
							5,
						);
						window.open(r.message.file_url, "_blank");
					}
				},
			});
		});
	},
});

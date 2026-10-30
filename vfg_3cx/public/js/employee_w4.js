// Buttons for Employee W4: public employee link (Step 1-4 self-service) and
// generate the filled official W-4 PDF (vfg_3cx.onboarding).

frappe.ui.form.on("Employee W4", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Get Employee Link"), () => {
			frappe.call({
				method: "vfg_3cx.onboarding.get_w4_link",
				args: { name: frm.doc.name },
				freeze: true,
				callback(r) {
					if (!r.message || !r.message.url) return;
					frm.reload_doc();
					if (r.message.already_signed) {
						frappe.msgprint({
							title: __("Already Signed"),
							indicator: "green",
							message: __("This employee has already filled and signed the W-4 form."),
						});
						return;
					}
					const safe = frappe.utils.escape_html(r.message.url);
					frappe.msgprint({
						title: __("Employee W-4 Link"),
						indicator: "blue",
						message: `
							<p>${__("Send this link to the employee. They complete the W-4 and sign — no login needed.")}</p>
							<input id="w4-url" class="form-control" value="${safe}" readonly onclick="this.select()" style="margin-bottom:8px;">
							<button class="btn btn-sm btn-primary"
								onclick="navigator.clipboard.writeText(document.getElementById('w4-url').value).then(function(){frappe.show_alert({message:__('Link copied'),indicator:'green'});})">
								${__("Copy link")}
							</button>
							<a href="${safe}" target="_blank" class="btn btn-sm btn-default">${__("Open link")}</a>`,
					});
				},
			});
		});

		frm.add_custom_button(__("Generate Filled W-4 PDF"), () => {
			frappe.call({
				method: "vfg_3cx.onboarding.generate_w4_pdf",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Filling the official W-4 form…"),
				callback(r) {
					if (r.message && r.message.file_url) {
						frm.reload_doc();
						frappe.show_alert({ message: __("W-4 PDF generated."), indicator: "green" }, 5);
						window.open(r.message.file_url, "_blank");
					}
				},
			});
		});
	},
});

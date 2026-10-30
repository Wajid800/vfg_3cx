// Adds a "Generate Link" button to Accounting Service Agreement ("On-Boarding").
// It creates a public, token-protected signing page and shows the URL (copy /
// open) to send to the client. They sign without any ERPNext login; the
// signature is written back to Client Signature (see vfg_3cx.sign).

frappe.ui.form.on("Accounting Service Agreement", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(
			__("Generate Link"),
			() => {
				frappe.call({
					method: "vfg_3cx.sign.get_doc_signature_link",
					args: { doctype: frm.doctype, name: frm.doc.name },
					freeze: true,
					freeze_message: __("Preparing signing link…"),
					callback(r) {
						if (!r.message || !r.message.url) return;
						const safe = frappe.utils.escape_html(r.message.url);
						frappe.msgprint({
							title: __("Signature Link"),
							indicator: "blue",
							message: `
								<p>${__("Send this link to the customer / client. They can open it, review the details and sign — no login needed.")}</p>
								<input id="vfg-sig-url" class="form-control" value="${safe}"
									readonly onclick="this.select()" style="margin-bottom:8px;">
								<button class="btn btn-sm btn-primary"
									onclick="navigator.clipboard.writeText(document.getElementById('vfg-sig-url').value).then(function(){frappe.show_alert({message:__('Link copied'),indicator:'green'});})">
									${__("Copy link")}
								</button>
								<a href="${safe}" target="_blank" class="btn btn-sm btn-default">
									${__("Open link")}
								</a>`,
						});
					},
				});
			},
			__("Signature"),
		);
	},
});

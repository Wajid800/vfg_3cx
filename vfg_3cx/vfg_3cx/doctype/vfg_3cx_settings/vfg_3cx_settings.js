// Copyright (c) 2026, Shahrukhar Sattar and contributors
// For license information, please see license.txt

frappe.ui.form.on("VFG 3CX Settings", {
	refresh(frm) {
		frm.add_custom_button(__("🔄 Sync to Asterisk"), function () {
			frappe.confirm(
				__(
					"Yeh action pjsip_agents.conf overwrite karega aur Asterisk reload hoga.<br><br>" +
					"Sirf tab click karein jab Agent Extensions table mein sab credentials fill hoon.<br><br>" +
					"<b>Continue?</b>"
				),
				function () {
					frappe.show_alert({ message: __("Asterisk config generate ho rahi hai..."), indicator: "blue" });
					frappe.call({
						method: "vfg_3cx.api.sync_asterisk_config",
						freeze: true,
						freeze_message: __("Asterisk config sync ho rahi hai — please wait..."),
						callback(r) {
							if (r.message && r.message.ok) {
								frappe.msgprint({
									title: __("✅ Sync Successful"),
									message:
										"<pre style='font-size:13px; white-space:pre-wrap;'>" +
										r.message.message +
										"</pre>",
									indicator: "green",
								});
							}
						},
					});
				}
			);
		}, __("Asterisk"));

		frm.add_custom_button(__("📋 Preview Config"), function () {
			frappe.call({
				method: "vfg_3cx.api.preview_asterisk_config",
				callback(r) {
					if (r.message) {
						let d = new frappe.ui.Dialog({
							title: __("Generated pjsip_agents.conf"),
							size: "extra-large",
						});
						d.body.innerHTML =
							"<pre style='background:#0D1526; color:#7DD3F7; padding:16px; border-radius:6px;" +
							"font-size:12px; line-height:1.7; overflow:auto; max-height:70vh;'>" +
							frappe.utils.escape_html(r.message) + "</pre>";
						d.show();
					}
				},
			});
		}, __("Asterisk"));
	},
});

const SESSION_KEY = "__company_dialog_done__";

// Trigger after route change
frappe.router.on("change", () => {
    if (!frappe.session || frappe.session.user === "Guest") return;
    if (frappe.user.has_role("System Manager")) return;
    if (sessionStorage.getItem(SESSION_KEY)) return;

    sessionStorage.setItem(SESSION_KEY, "1");
    setTimeout(show_company_dialog, 300);
});

function show_company_dialog() {
    $("body").addClass("company-locked");

    const dialog = new frappe.ui.Dialog({
        title: "Select Company and Territory",
        static: true,
        animate: false,
        fields: [
            {
                fieldname: "company",
                label: "Company",
                fieldtype: "Link",
                options: "Company",
                reqd: 1,
            },
            {
                fieldname: "territory",
                label: "Territory",
                fieldtype: "Link",
                options: "Territory",
                reqd: 1,
            },
        ],
        primary_action_label: "Enter Application",
        primary_action(values) {
            if (!values.company || !values.territory) {
                frappe.msgprint("Please select Company and Territory");
                return;
            }

            frappe.call({
                method: "ch_erp15.api.set_login_context",
                args: values,
                callback() {
                    dialog.hide();
                    $("body").removeClass("company-locked");
                    location.reload();
                }
            });
        }
    });

    dialog.show();

    // 🚫 Remove close button
    dialog.$wrapper.find(".modal-header .close").remove();

    // 🚫 Disable ESC and backdrop click
    dialog.$wrapper.attr("data-backdrop", "static");
    dialog.$wrapper.attr("data-keyboard", "false");

    // 🚫 Block browser back
    history.pushState(null, "", location.href);
    window.onpopstate = () => history.pushState(null, "", location.href);
}

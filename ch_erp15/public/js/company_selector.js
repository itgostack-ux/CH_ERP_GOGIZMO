console.log("✅ Company selector loaded");

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
        title: "Select Company, City and Zone",
        static: true,
        animate: false,
        fields: [
            {
                fieldname: "company",
                label: "Company",
                fieldtype: "Link",
                options: "Company",
                reqd: 1,
                change() {
                    // Reset dependent fields
                    dialog.set_value("city", "");
                    dialog.set_value("zone", "");

                    // Company → City filter
                    dialog.set_df_property("city", "get_query", () => ({
                        query: "ch_erp15.api.get_company_cities",
                        filters: {
                            company_name: dialog.get_value("company")
                        }
                    }));

                    // Company → Zone filter
                    dialog.set_df_property("zone", "get_query", () => ({
                        query: "ch_erp15.api.get_company_zones",
                        filters: {
                            company_name: dialog.get_value("company")
                        }
                    }));
                }
            },
            {
                fieldname: "city",
                label: "City",
                fieldtype: "Link",
                options: "City",
                reqd: 1
            },
            {
                fieldname: "zone",
                label: "Zone",
                fieldtype: "Link",
                options: "Zone",
                reqd: 1
            }
        ],
        primary_action_label: "Enter Application",
        primary_action(values) {
            if (!values.company || !values.city || !values.zone) {
                frappe.msgprint("Please select Company, City and Zone");
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

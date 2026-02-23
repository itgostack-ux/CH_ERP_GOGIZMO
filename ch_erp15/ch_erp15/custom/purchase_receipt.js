frappe.ui.form.on("Purchase Receipt", {

    refresh(frm) {
        toggle_all_tax_fields(frm);
    },

    onload(frm) {
        toggle_all_tax_fields(frm);
    },

    custom_purchase_type(frm) {
        toggle_all_tax_fields(frm);
    }

});


function toggle_all_tax_fields(frm) {

    const is_unregistered = frm.doc.custom_purchase_type === "Unregistered";

    // Hide tax fields
    frm.set_df_property("taxes_section", "hidden", is_unregistered);
    frm.set_df_property("taxes_and_charges", "hidden", is_unregistered);
    frm.set_df_property("tax_category", "hidden", is_unregistered);
    frm.set_df_property("taxes", "hidden", is_unregistered);

    // Hide totals
    frm.set_df_property("total_taxes_and_charges", "hidden", is_unregistered);
    frm.set_df_property("base_total_taxes_and_charges", "hidden", is_unregistered);

    // Clear taxes automatically
    if (is_unregistered) {
        frm.clear_table("taxes");
        frm.set_value("taxes_and_charges", "");
        frm.set_value("tax_category", "");
    }

    frm.refresh_fields([
        "taxes_and_charges",
        "tax_category",
        "taxes",
        "total_taxes_and_charges",
        "base_total_taxes_and_charges"
    ]);
}
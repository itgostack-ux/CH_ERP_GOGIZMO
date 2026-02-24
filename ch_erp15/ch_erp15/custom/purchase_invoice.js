// frappe.ui.form.on("Purchase Invoice", {

//     refresh(frm) {
//         toggle_all_tax_fields(frm);
//     },

//     onload(frm) {
//         toggle_all_tax_fields(frm);
//     },

//     custom_purchase_type(frm) {
//         toggle_all_tax_fields(frm);
//     }

// });


// function toggle_all_tax_fields(frm) {

//     const is_unregistered = frm.doc.custom_purchase_type === "Unregistered";

//     frm.set_df_property("taxes_and_charges", "hidden", is_unregistered);
//     frm.set_df_property("tax_category", "hidden", is_unregistered);
//     frm.set_df_property("taxes", "hidden", is_unregistered);

//     frm.set_df_property("total_taxes_and_charges", "hidden", is_unregistered);
//     frm.set_df_property("base_total_taxes_and_charges", "hidden", is_unregistered);

//     if (is_unregistered) {
//         frm.clear_table("taxes");
//         frm.set_value("taxes_and_charges", "");
//         frm.set_value("tax_category", "");
//     }

//     frm.refresh_fields([
//         "taxes_and_charges",
//         "tax_category",
//         "taxes",
//         "total_taxes_and_charges",
//         "base_total_taxes_and_charges"
//     ]);
// }
frappe.ui.form.on("Purchase Invoice", {

    onload_post_render(frm) {
        zero_tax_if_unregistered(frm);
    },

    refresh(frm) {
        zero_tax_if_unregistered(frm);
    },

    custom_purchase_type(frm) {
        zero_tax_if_unregistered(frm);
    },

    supplier(frm) {
        zero_tax_if_unregistered(frm);
    },

    items_add(frm) {
        zero_tax_if_unregistered(frm);
    },

    validate(frm) {
        zero_tax_if_unregistered(frm);
    }

});
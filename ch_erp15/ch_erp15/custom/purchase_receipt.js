frappe.ui.form.on("Purchase Receipt", {

    // onload(frm) {
    //     apply_zero_tax(frm);
    //     apply_marginal_scheme(frm);
    // },

    // refresh(frm) {
    //     apply_zero_tax(frm);
    //     apply_marginal_scheme(frm);
    // },

    // custom_purchase_type(frm) {
    //     apply_zero_tax(frm);
    //     apply_marginal_scheme(frm);
    // },

    validate(frm) {
        apply_marginal_scheme(frm);

        // Ensure IMEI child table has valid data
        if (frm.doc.custom_track && frm.doc.custom_track.length > 0) {
            let duplicate_check = {};
            for (let d of frm.doc.custom_track) {
                if (!d.imei_number) {
                    frappe.throw("All IMEI numbers are required.");
                }
                if (duplicate_check[d.imei_number]) {
                    frappe.throw(`Duplicate IMEI number found: ${d.imei_number}`);
                }
                duplicate_check[d.imei_number] = true;
            }
        }
    },

    before_save(frm) {
        apply_zero_tax(frm);
        apply_marginal_scheme(frm);
    },

    before_submit(frm) {
        apply_zero_tax(frm);
        apply_marginal_scheme(frm);
    }
});

frappe.ui.form.on("Purchase Receipt Item", {

    qty(frm, cdt, cdn) {
        apply_marginal_scheme(frm);
    },

    rate(frm, cdt, cdn) {
        apply_marginal_scheme(frm);
    },

    custom_unit_taxable_value(frm, cdt, cdn) {
        apply_marginal_scheme(frm);
    },

    custom_imei_track(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.custom_imei_track) return;

        if (!row.qty || row.qty <= 0) {
            frappe.msgprint("Please enter Qty first");
            frappe.model.set_value(cdt, cdn, "custom_imei_track", 0);
            return;
        }

        open_imei_dialog(frm, row);
    }

});

frappe.ui.form.on("Purchase Taxes and Charges", {

    rate(frm, cdt, cdn) {
        apply_marginal_scheme(frm);
    }

});

function apply_zero_tax(frm) {
    const is_unregistered = frm.doc.custom_purchase_type === "Unregistered";

    if (is_unregistered) {
        (frm.doc.taxes || []).forEach(row => {
            row.rate = 0;
            row.tax_amount = 0;
            row.base_tax_amount = 0;
            row.total = 0;
            row.base_total = 0;
        });

        frm.refresh_field("taxes");

        frm.set_value("total_taxes_and_charges", 0);
        frm.set_value("base_total_taxes_and_charges", 0);

        frm.trigger("calculate_taxes_and_totals");
    }
}

function apply_marginal_scheme(frm) {

    if (frm.doc.custom_purchase_type !== "Marginal") return;

    let total_margin_taxable = 0.0;
    let total_gst = 0.0;
    let total_exempted = 0.0;

    (frm.doc.items || []).forEach(item => {
        let qty = flt(item.qty);
        let rate = flt(item.rate);
        let margin_unit = flt(item.custom_unit_taxable_value);

        if (qty <= 0 || rate <= 0 || margin_unit < 0) return;

        let item_amount = qty * rate;
        let margin_taxable = qty * margin_unit;

        item.amount = item_amount;
        item.base_amount = item_amount;
        item.taxable_value = margin_taxable;

        total_margin_taxable += margin_taxable;
    });

    frm.refresh_field("items");

    (frm.doc.taxes || []).forEach(tax => {
        tax.tax_amount = 0;
        tax.amount = 0;
        tax.total = 0;

        if (tax.charge_type === "On Net Total") {
            let tax_amount = (total_margin_taxable * flt(tax.rate)) / 100;

            tax.tax_amount = tax_amount;
            tax.amount = tax_amount;
            tax.total = tax_amount;

            tax.base_tax_amount = tax_amount;
            tax.base_amount = tax_amount;

            total_gst += tax_amount;
        }
    });

    frm.refresh_field("taxes");

    (frm.doc.items || []).forEach(item => {
        let qty = flt(item.qty);
        let rate = flt(item.rate);
        let margin_unit = flt(item.custom_unit_taxable_value);

        if (qty <= 0 || flt(item.amount) <= 0) return;

        let margin_taxable = qty * margin_unit;
        let gst_share = total_margin_taxable ? (margin_taxable / total_margin_taxable) * total_gst : 0;

        let exempted_value = flt(item.amount) - margin_taxable - gst_share;
        if (exempted_value < 0) exempted_value = 0;

        item.custom_exempted_value = exempted_value;
        total_exempted += exempted_value;
    });

    frm.refresh_field("items");

    let grand_total = total_margin_taxable + total_gst + total_exempted;

    frm.set_value("net_total", total_margin_taxable);
    frm.set_value("base_net_total", total_margin_taxable);

    frm.set_value("total_taxes_and_charges", total_gst);
    frm.set_value("base_total_taxes_and_charges", total_gst);

    frm.set_value("taxes_and_charges_added", total_gst);
    frm.set_value("base_taxes_and_charges_added", total_gst);

    frm.set_value("grand_total", grand_total);
    frm.set_value("base_grand_total", grand_total);
    frm.set_value("rounded_total", Math.round(grand_total));

    frm.set_value("custom_margin_taxable", total_margin_taxable);
    frm.set_value("custom_margin_gst", total_gst);
    frm.set_value("custom_exempted_value", total_exempted);

    frm.refresh_fields([
        "net_total",
        "taxes_and_charges_added",
        "grand_total",
        "rounded_total",
        "custom_margin_taxable",
        "custom_margin_gst",
        "custom_exempted_value"
    ]);
}

function open_imei_dialog(frm, row) {

    let table_data = [];
    for (let i = 0; i < row.qty; i++) {
        table_data.push({ item_code: row.item_code, imei_no: "" });
    }

    let dialog = new frappe.ui.Dialog({
        title: "IMEI Entry",
        size: "large",
        fields: [
            {
                fieldname: "imei_table",
                fieldtype: "Table",
                label: "IMEI Numbers",
                reqd: 1,
                in_place_edit: true,
                data: table_data,
                fields: [
                    { fieldtype: "Data", fieldname: "item_code", label: "Item Code", read_only: 1, in_list_view: 1 },
                    { fieldtype: "Data", fieldname: "imei_no", label: "IMEI Number", reqd: 1, in_list_view: 1 }
                ]
            }
        ],

        primary_action_label: "Save",
        primary_action() {
            let imeis = dialog.fields_dict.imei_table.grid.get_data();

            if (!imeis.length || imeis.some(d => !d.imei_no)) {
                frappe.msgprint("All IMEI numbers are required");
                return;
            }

            let list = imeis.map(d => d.imei_no);
            if (new Set(list).size !== list.length) {
                frappe.msgprint("Duplicate IMEI numbers found");
                return;
            }

            frm.doc.custom_track = (frm.doc.custom_track || []).filter(
                d => d.purchase_receipt_item !== row.name
            );

            imeis.forEach(d => {
                let child = frm.add_child("custom_track");
                child.item_code = row.item_code;
                child.imei_number = d.imei_no;
                child.purchase_receipt_item = row.name;
            });

            frm.refresh_field("custom_track");
            frm.dirty();

            frappe.show_alert({ message: "IMEI saved successfully", indicator: "green" });
            dialog.hide();
        }
    });

    dialog.show();
}
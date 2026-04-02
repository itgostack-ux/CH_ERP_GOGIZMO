
frappe.ui.form.on("Purchase Receipt", {
 
    refresh(frm) {
        apply_zero_tax(frm);
        apply_marginal_scheme(frm);
        apply_taxable_scheme(frm);

        // Barcode sticker printing buttons (only after submit)
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Print All Barcode Stickers"), () => {
                _print_barcode_stickers(frm);
            }, __("Barcode"));

            frm.add_custom_button(__("Print Specific Barcodes"), () => {
                _print_specific_barcodes(frm);
            }, __("Barcode"));
        }
    },
 
    onload(frm) {
        frm.cscript = frm.cscript || {};
        if (!frm._original_calculation) {
            frm._original_calculation = frm.cscript.calculate_taxes_and_totals;
        }
        frm.cscript.calculate_taxes_and_totals = function () {
            if (frm.doc.custom_purchase_type === "Marginal") {
                apply_zero_tax(frm);
                apply_marginal_scheme(frm);
                apply_taxable_scheme(frm);
 
                return;
            }
            if (frm._original_calculation) {
                frm._original_calculation.call(frm);
            }
        };
    },
 
    before_save: async function (frm) {
        apply_zero_tax(frm);
        apply_marginal_scheme(frm);
        apply_taxable_scheme(frm);
 
        let all_serials = [];
 
        (frm.doc.items || []).forEach(item => {
 
            if (!item.custom_imei) {
                frappe.throw(`Please select IMEI option (Yes/No) for Item ${item.item_code}`);
            }
 
            item.serial_and_batch_bundle = null;
 
            let list = (item.serial_no || "")
                .split("\n")
                .map(i => i.trim())
                .filter(i => i);
 
            if (item.custom_imei === "Yes") {
                if (list.length !== item.qty) {
                    frappe.throw(`IMEI count must match Qty for Item ${item.item_code}`);
                }
            }
 
            if (item.custom_imei === "No") {
                if (!item.serial_no) {
                    frappe.throw(`Serial No is mandatory for Item ${item.item_code}`);
                }
 
                if (list.length !== item.qty) {
                    frappe.throw(`Serial count must match Qty for Item ${item.item_code}`);
                }
            }
 
            all_serials.push(...list);
        });
 
        if (all_serials.length) {
 
            let existing = await frappe.db.get_list("Serial No", {
                filters: { name: ["in", all_serials] },
                fields: ["name", "warehouse", "status"]
            });
 
           
        }
    },
 
    custom_purchase_type(frm) {
        apply_zero_tax(frm);
        apply_marginal_scheme(frm);
        apply_taxable_scheme(frm);
 
    },
 
    validate(frm) {
        apply_marginal_scheme(frm);
        apply_taxable_scheme(frm);
        apply_zero_tax(frm);
 
 
        // Ensure IMEI child table has valid data
        (frm.doc.items || []).forEach(item => {
 
            if (item.custom_imei === "No") {
 
                 if (!item.serial_no || !item.serial_no.trim()) {
                     frappe.throw(`Serial No is mandatory for Item ${item.item_code}`);
                 }
 
                let serial_list = item.serial_no
                    .split("\n")
                    .map(i => i.trim())
                    .filter(i => i);
 
                 if (serial_list.length !== item.qty) {
                     frappe.throw(`Serial count must match Qty for Item ${item.item_code}`);
                 }
 
                 if (new Set(serial_list).size !== serial_list.length) {
                     frappe.throw(`Duplicate Serial No found for Item ${item.item_code}`);
                }
            }
 
            item.serial_and_batch_bundle = null;
        });
    }
 
 
 
});
 
 
frappe.ui.form.on("Purchase Receipt Item", {
 
    qty: async function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
 
        apply_marginal_scheme(frm);
        apply_taxable_scheme(frm);
        apply_zero_tax(frm);
 
 
        if (row.custom_imei === "No") {
 
            frappe.model.set_value(cdt, cdn, "serial_no", "");
 
            await generate_auto_serial(frm, row);
        }
 
        if (row.custom_imei === "Yes") {
            if (!row.qty || row.qty <= 0) return;
 
            frappe.model.set_value(cdt, cdn, "serial_no", "");
            open_imei_dialog(frm, row);
        }
    },
 
 
    rate(frm, cdt, cdn) {
        apply_marginal_scheme(frm);
        apply_zero_tax(frm);
 
    },
 
    custom_unit_taxable_value(frm, cdt, cdn) {
        apply_marginal_scheme(frm);
        apply_taxable_scheme(frm);
       
       
    },
 
    custom_imei: async function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
 
        if (row.custom_imei === "Yes") {
 
            if (!row.qty || row.qty <= 0) {
                frappe.msgprint("Please enter Qty first");
                frappe.model.set_value(cdt, cdn, "custom_imei", "No");
                return;
            }
 
            frappe.model.set_value(cdt, cdn, "serial_no", "");
            open_imei_dialog(frm, row);
 
        } else {
            await generate_auto_serial(frm, row);
        }
 
        toggle_imei_field(frm, row);
    },
 
    item_code(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
 
        if (row.item_code) {
            frappe.db.get_value("Item", row.item_code,
                ["has_serial_no", "serial_no_series"],
                (r) => {
 
                    frappe.model.set_value(cdt, cdn, "has_serial_no", r.has_serial_no);
                    frappe.model.set_value(cdt, cdn, "serial_no_series", r.serial_no_series);
 
                }
            );
        }
    },
 
 
});
 
 
 
frappe.ui.form.on("Purchase Taxes and Charges", {
 
    rate(frm, cdt, cdn) {
        apply_marginal_scheme(frm);
        apply_taxable_scheme(frm);
    }
 
});
 
 
 
 
function apply_zero_tax(frm) {
 
    if (frm.doc.custom_purchase_type !== "Unregistered") return;
 
    let total_amount = 0;
 
    (frm.doc.items || []).forEach(item => {
 
        let qty = flt(item.qty);
        let rate = flt(item.rate);
 
        let amount = qty * rate;
 
        item.amount = amount;
        item.base_amount = amount;
 
        total_amount += amount;
    });
 
    (frm.doc.taxes || []).forEach(row => {
 
 
        row.tax_amount = 0;
        row.base_tax_amount = 0;
 
        row.total = total_amount;
        row.base_total = total_amount;
    });
 
    frm.doc.net_total = total_amount;
    frm.doc.base_net_total = total_amount;
 
    frm.doc.total = total_amount;
    frm.doc.base_total = total_amount;
 
    frm.doc.total_taxes_and_charges = 0;
    frm.doc.base_total_taxes_and_charges = 0;
 
    frm.doc.taxes_and_charges_added = 0;
    frm.doc.base_taxes_and_charges_added = 0;
 
    frm.doc.grand_total = total_amount;
    frm.doc.base_grand_total = total_amount;
 
    frm.doc.rounded_total = Math.round(total_amount);
    frm.doc.base_rounded_total = Math.round(total_amount);
 
    frm.refresh_fields([
        "items",
        "taxes",
        "net_total",
        "grand_total",
        "rounded_total"
    ]);
}
 
 
 
function apply_marginal_scheme(frm) {
 
    if (frm.doc.custom_purchase_type !== "Marginal") {
        return;
    }
 
    let total_margin_taxable = 0;
    let total_gst = 0;
    let total_exempted = 0;
 
    //--------------------------------------------------
    // ITEM LEVEL
    //--------------------------------------------------
 
    (frm.doc.items || []).forEach(item => {
 
        let qty = flt(item.qty);
        let rate = flt(item.rate);
        let margin_unit = flt(item.custom_unit_taxable_value);
 
        if (qty <= 0 || rate <= 0 || margin_unit <= 0) return;
 
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
        let margin_unit = flt(item.custom_unit_taxable_value);
 
        if (qty <= 0 || flt(item.amount) <= 0) return;
 
        let margin_taxable = qty * margin_unit;
 
        let item_gst = 0;
        if (total_margin_taxable > 0) {
            item_gst = (margin_taxable / total_margin_taxable) * total_gst;
        }
 
        let exempted_value = flt(item.amount) - margin_taxable - item_gst;
 
        if (exempted_value < 0) {
            exempted_value = 0;
        }
 
        item.custom_exempted_value = exempted_value;
 
        total_exempted += exempted_value;
 
    });
 
    frm.refresh_field("items");
 
 
    frm.doc.net_total = total_margin_taxable;
    frm.doc.base_net_total = total_margin_taxable;
 
    frm.doc.taxes_and_charges_added = total_gst;
    frm.doc.base_taxes_and_charges_added = total_gst;
 
    frm.doc.total_taxes_and_charges = total_gst;
    frm.doc.base_total_taxes_and_charges = total_gst;
 
    let custom_grand_total = total_margin_taxable + total_gst + total_exempted;
 
    frm.doc.grand_total = custom_grand_total;
    frm.doc.base_grand_total = custom_grand_total;
    frm.doc.rounded_total = Math.round(custom_grand_total);
 
    frm.refresh_fields([
        "net_total",
        "taxes_and_charges_added",
        "grand_total",
        "rounded_total"
    ]);
}
 
 
 
 
 
function apply_taxable_scheme(frm) {
 
    if (frm.doc.custom_purchase_type !== "Taxable") return;
 
    let total_taxable = 0;
    let total_gst = 0;
 
    (frm.doc.items || []).forEach(item => {
 
        let qty = flt(item.qty);
        let unit_taxable = flt(item.custom_unit_taxable_value);
 
        if (qty <= 0 || unit_taxable <= 0) {
            item.rate = 0;
            item.amount = 0;
            item.base_amount = 0;
            item.taxable_value = 0;
            return;
        }
 
        let rate = unit_taxable * 1.18;
        let amount = qty * rate;
        let taxable_value = qty * unit_taxable;
 
        item.rate = rate;
        item.amount = amount;
        item.base_amount = amount;
        item.taxable_value = taxable_value;
 
        total_taxable += taxable_value;
    });
 
    frm.refresh_field("items");
    total_gst = total_taxable * 0.18;
 
    (frm.doc.taxes || []).forEach(tax => {
 
        tax.tax_amount = total_gst;
        tax.amount = total_gst;
        tax.total = total_gst;
 
        tax.base_tax_amount = total_gst;
        tax.base_amount = total_gst;
    });
 
    frm.refresh_field("taxes");
 
    let gross_total = total_taxable + total_gst;
    let discount = flt(frm.doc.discount_amount);
 
    let final_total = gross_total - discount;
 
    if (final_total < 0) final_total = 0;
 
    frm.doc.net_total = total_taxable;
    frm.doc.base_net_total = total_taxable;
 
    frm.doc.total_taxes_and_charges = total_gst;
    frm.doc.base_total_taxes_and_charges = total_gst;
 
    frm.doc.taxes_and_charges_added = total_gst;
    frm.doc.base_taxes_and_charges_added = total_gst;
 
    frm.doc.grand_total = final_total;
    frm.doc.base_grand_total = final_total;
 
    frm.doc.rounded_total = Math.round(final_total);
    frm.doc.base_rounded_total = Math.round(final_total);
 
    frm.refresh_fields([
        "net_total",
        "total_taxes_and_charges",
        "grand_total",
        "rounded_total",
        "discount_amount"
    ]);
}
 
 
 

 
 
 
 
 
 
 
 
 
 
function open_imei_dialog(frm, row) {
    let existing_imeis = [];
 
    if (row.serial_no) {
        existing_imeis = row.serial_no
            .split("\n")
            .map(i => i.trim())
            .filter(i => i);
    }
 
    let table_data = [];
 
    existing_imeis.forEach(imei => {
        table_data.push({ item_code: row.item_code, imei_no: imei });
    });
 
    // Fill empty rows for remaining quantity
    for (let i = existing_imeis.length; i < row.qty; i++) {
        table_data.push({ item_code: row.item_code, imei_no: "" });
    }
 
    let dialog = new frappe.ui.Dialog({
        title: "IMEI Entry",
        size: "large",
        fields: [
            {
                fieldname: "scanner_input",
                fieldtype: "Data",
                label: "Scan IMEI",
                placeholder: "Scan IMEI here (auto-update)",
            },
            {
                fieldname: "imei_table",
                fieldtype: "Table",
                label: "IMEI Numbers",
                reqd: 1,
                in_place_edit: true,
                data: table_data,
                fields: [
                    { fieldtype: "Data", fieldname: "item_code", label: "Item Code", read_only: 1, in_list_view: 1 },
                    { fieldtype: "Data", fieldname: "imei_no", label: "IMEI Number", read_only: 1, reqd: 1, in_list_view: 1 }
                ]
            }
        ],
 
        primary_action_label: "Save",
        primary_action() {
            let imeis = dialog.fields_dict.imei_table.grid.get_data();
 
            let list = imeis.map(d => d.imei_no.trim());
 
            if (list.some(i => !i)) {
                frappe.throw("All IMEI slots must be filled");
            }
 
            if (new Set(list).size !== list.length) {
                frappe.throw("Duplicate IMEI numbers found");
            }
 
            if (list.length !== row.qty) {
                frappe.throw("IMEI count must match Qty");
            }
            row.serial_no = list.join("\n");
            frm.refresh_field("items");
 
            frappe.show_alert({ message: "IMEI saved successfully", indicator: "green" });
            dialog.hide();
        }
    });
 
    dialog.show();
 
 
    let scanner_input = dialog.fields_dict.scanner_input.$input;
 
    scanner_input.on("keydown", async function (e) {
 
        if (e.key !== "Enter") return;
 
        e.preventDefault();
 
        let val = scanner_input.val().trim();
        if (!val) return;
 
        let imei_table = dialog.fields_dict.imei_table.grid.get_data();
 
        if (imei_table.some(d => d.imei_no === val)) {
            frappe.msgprint(`IMEI ${val} already entered`);
            scanner_input.val("");
            return;
        }
 
        let existing = await frappe.db.get_list("Serial No", {
            filters: { name: val },
            fields: ["name", "status"],
            limit: 1
        });
 
        if (existing.length > 0) {
            let status = existing[0].status;
 
            if (status !== "Delivered") {
                frappe.msgprint(`IMEI ${val} already exists`);
                scanner_input.val("");
                return;
            }
        }
 
        let empty_row = imei_table.find(d => !d.imei_no);
 
        if (!empty_row) {
            frappe.msgprint("All IMEI slots are filled");
            scanner_input.val("");
            return;
        }
 
        empty_row.imei_no = val;
 
        dialog.fields_dict.imei_table.grid.refresh();
 
        scanner_input.val("");
    });
}
 
async function generate_auto_serial(frm, row) {
    if (!row.item_code || !row.qty) return;
    if (row.custom_imei === "Yes") return;
 
    if (row.serial_no && row.serial_no.trim()) return;
    let item = await frappe.db.get_value("Item", row.item_code, "serial_no_series");
 
    let series = item.message.serial_no_series || row.item_code + "-.#####";
 
    let prefix = series.split("#")[0].replace(".", "");
 
    let all_serials = await frappe.db.get_list("Serial No", {
        filters: { item_code: row.item_code },
        fields: ["name", "status"],
        order_by: "creation asc",
        limit: 1000
    });
 
    let last_number = 0;
    let reused_serials = [];
 
    for (let s of all_serials) {
        let match = s.name.match(new RegExp(`^${prefix}(\\d+)$`));
        if (match) {
            let num = parseInt(match[1]);
            last_number = Math.max(last_number, num);
 
            if (s.status === "Delivered") {
                reused_serials.push({ name: s.name, number: num });
            }
        }
    }
 
    reused_serials.sort((a, b) => a.number - b.number);
 
    let serials_to_assign = [];
    let qty = row.qty;
 
    frm._reused_serials = frm._reused_serials || [];
 
    for (let i = 0; i < reused_serials.length && serials_to_assign.length < qty; i++) {
        let sn = reused_serials[i].name;
 
        serials_to_assign.push(sn);
 
        if (!frm._reused_serials.includes(sn)) {
            frm._reused_serials.push(sn);
        }
    }
 
    let remaining = qty - serials_to_assign.length;
 
    for (let i = 0; i < remaining; i++) {
        last_number++;
        serials_to_assign.push(
            `${prefix}${String(last_number).padStart(5, "0")}`
        );
    }
 
    row.serial_no = serials_to_assign.join("\n");
    row.has_serial_no = true;
 
    frm.refresh_field("items");
}
 
function toggle_imei_field(frm, row) {
    let grid = frm.fields_dict["items"].grid;
 
    let must_enable_serial = row.custom_imei === "No";
 
    grid.update_docfield_property(
        "serial_no",
        "read_only",
        !must_enable_serial
    );
 
    row.has_serial_no = must_enable_serial;
 
    frm.refresh_field("items");
}

// ── Barcode Sticker Printing ─────────────────────────────────────
function _print_barcode_stickers(frm) {
    // Collect all serial numbers from the Purchase Receipt
    const serials = [];
    (frm.doc.items || []).forEach((item) => {
        const sn_list = (item.serial_no || "").split("\n").map(s => s.trim()).filter(Boolean);
        sn_list.forEach((sn) => {
            serials.push({ serial_no: sn, item_code: item.item_code, item_name: item.item_name });
        });
    });
    if (!serials.length) {
        frappe.msgprint(__("No serial numbers found in this Purchase Receipt."));
        return;
    }
    _open_barcode_print_window(serials, frm.doc.name);
}

function _print_specific_barcodes(frm) {
    // Let user select specific serial numbers to reprint
    const all_serials = [];
    (frm.doc.items || []).forEach((item) => {
        const sn_list = (item.serial_no || "").split("\n").map(s => s.trim()).filter(Boolean);
        sn_list.forEach((sn) => {
            all_serials.push({ serial_no: sn, item_code: item.item_code, item_name: item.item_name });
        });
    });
    if (!all_serials.length) {
        frappe.msgprint(__("No serial numbers found."));
        return;
    }

    const fields = all_serials.map((s, i) => ({
        fieldname: `sn_${i}`,
        fieldtype: "Check",
        label: `${s.serial_no} — ${s.item_name}`,
        default: 0,
    }));

    const d = new frappe.ui.Dialog({
        title: __("Select Barcodes to Print"),
        fields: fields,
        size: "large",
        primary_action_label: __("Print Selected"),
        primary_action: (values) => {
            const selected = [];
            all_serials.forEach((s, i) => {
                if (values[`sn_${i}`]) selected.push(s);
            });
            if (!selected.length) {
                frappe.msgprint(__("No barcodes selected."));
                return;
            }
            d.hide();
            _open_barcode_print_window(selected, frm.doc.name);
        },
    });
    d.show();
}

function _open_barcode_print_window(serials, receipt_name) {
    // Generate barcode sticker HTML and open in a new print window
    const stickers = serials.map((s) => `
        <div class="barcode-sticker">
            <div class="sticker-item-name">${frappe.utils.escape_html(s.item_name)}</div>
            <div class="sticker-item-code">${frappe.utils.escape_html(s.item_code)}</div>
            <svg class="barcode-svg" data-serial="${frappe.utils.escape_html(s.serial_no)}"></svg>
            <div class="sticker-serial">${frappe.utils.escape_html(s.serial_no)}</div>
        </div>
    `).join("");

    const html = `<!DOCTYPE html>
<html>
<head>
    <title>Barcode Stickers — ${frappe.utils.escape_html(receipt_name)}</title>
    <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.6/dist/JsBarcode.all.min.js"><\/script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; }
        .barcode-container {
            display: flex; flex-wrap: wrap; gap: 4mm;
            padding: 4mm; justify-content: flex-start;
        }
        .barcode-sticker {
            width: 50mm; height: 30mm; border: 0.5px solid #ccc;
            padding: 2mm; text-align: center; display: flex;
            flex-direction: column; align-items: center; justify-content: center;
            page-break-inside: avoid;
        }
        .sticker-item-name {
            font-size: 7pt; font-weight: bold;
            overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
            max-width: 46mm;
        }
        .sticker-item-code { font-size: 6pt; color: #666; margin-bottom: 1mm; }
        .barcode-svg { max-width: 44mm; height: 14mm; }
        .sticker-serial { font-size: 7pt; font-weight: 600; margin-top: 0.5mm; }
        @media print {
            body { margin: 0; }
            .barcode-sticker { border: 0.5px solid #ddd; }
            .no-print { display: none; }
            @page { margin: 5mm; }
        }
    </style>
</head>
<body>
    <div class="no-print" style="padding:10px;text-align:center;">
        <button onclick="window.print()" style="padding:8px 24px;font-size:14px;cursor:pointer;">
            🖨️ Print Stickers
        </button>
        <span style="margin-left:12px;color:#666;">${serials.length} sticker(s)</span>
    </div>
    <div class="barcode-container">${stickers}</div>
    <script>
        document.querySelectorAll(".barcode-svg").forEach(function(svg) {
            var serial = svg.getAttribute("data-serial");
            try {
                JsBarcode(svg, serial, {
                    format: "CODE128", width: 1.5, height: 40,
                    displayValue: false, margin: 0
                });
            } catch(e) {
                svg.parentNode.querySelector(".sticker-serial").style.color = "red";
            }
        });
    <\/script>
</body>
</html>`;

    const w = window.open("", "_blank");
    w.document.write(html);
    w.document.close();
}
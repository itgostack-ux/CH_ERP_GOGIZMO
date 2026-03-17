frappe.ui.form.on('Sales Order', {
    refresh(frm) {

        frm.add_custom_button("Open Scanner", function () {

            if (!frappe.ui.Scanner) {
                frappe.msgprint("Scanner not supported in this browser");
                return;
            }

            const scanner = new frappe.ui.Scanner({
                dialog: true,
                multiple: false,
                on_scan(data) {

                    let barcode = data.decodedText;

                    frappe.msgprint("Scanned: " + barcode);

                    // Example: add item automatically
                    frappe.call({
                        method: "frappe.client.get_value",
                        args: {
                            doctype: "Item Barcode",
                            filters: { barcode: barcode },
                            fieldname: ["parent"]
                        },
                        callback: function(r) {
                            if (r.message) {
                                let row = frm.add_child("items");
                                row.item_code = r.message.parent;
                                row.qty = 1;
                                frm.refresh_field("items");
                            }
                        }
                    });

                }
            });

        });

    }
});
# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

from io import BytesIO
import frappe
import xlsxwriter
from datetime import date, datetime

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": "Purchase Order ID",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 170
        },
        {
            "label": "Purchase Invoice ID",
            "fieldname": "purchase_invoice",
            "fieldtype": "Link",
            "options": "Purchase Invoice",
            "width": 170
        },
        {
            "label": "Category",
            "fieldname": "category",
            "fieldtype": "Link",
            "options": "CH Category",
            "width": 120
        },
        {
            "label": "Sub Category",
            "fieldname": "sub_category",
            "fieldtype": "Link",
            "options": "CH Sub Category",
            "width": 230
        },
        {
            "label": "Brand",
            "fieldname": "brand",
            "fieldtype": "Link",
            "options": "Brand",
            "width": 180
        },
        {
            "label": "Item",
            "fieldname": "item",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "IMEI",
            "fieldname": "imei",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Warehouse",
            "fieldname": "warehouse",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "Supplier Name",
            "fieldname": "supplier_name",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "Purchase Category",
            "fieldname": "purchase_category",
            "fieldtype": "Data",
            "width": 170
        },
        {
            "label": "Per Cost",
            "fieldname": "per_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Purchase Exempted",
            "fieldname": "purchase_exempted",
            "fieldtype": "Currency",
            "width": 170
        },
        {
            "label": "Purchase Taxable",
            "fieldname": "purchase_taxable",
            "fieldtype": "Currency",
            "width": 170
        },
        {
            "label": "Tax Amount",
            "fieldname": "tax_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Tax Rate",
            "fieldname": "tax_rate",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Tax Category",
            "fieldname": "tax_category",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Days Elapsed",
            "fieldname": "days_elapsed",
            "fieldtype": "int",
            "width": 120
        },
        {
            "label": "Current Status",
            "fieldname": "current_status",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Purchase Receipt No.",
            "fieldname": "pur_rec_no",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 170
        },
        {
            "label": "Available In",
            "fieldname": "available_in",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "State",
            "fieldname": "state",
            "fieldtype": "Data",
            "width": 150
        }
    ]

def get_data(filters):

    result = frappe.db.sql(get_query(filters), as_dict=True)
    today = date.today()

    data = []
    for row in result:
        days_elapsed= (today - row.posting_date).days
        data.append([
            row.order_id,
            row.invoice_id,
            row.category,
            row.sub_category,
            row.brand,
            row.item,
            row.imei,
            row.warehouse,
            row.supplier_name,
            row.purchase_category,
            row.per_cost,
            row.purchase_exempted,
            row.purchase_taxable,
            row.tax_amount,
            f"{int(row.tax_rate)}%",
            row.tax_category,
            days_elapsed,
            row.current_status,
            row.pur_rec_no,
            row.available_in,
            row.state
        ])
    return data

def get_query(filters):
    conditions = ""

    if filters.get("from_date") and filters.get("to_date"):
        conditions += f""" AND tpr.posting_date BETWEEN '{filters["from_date"]}' AND '{filters["to_date"]}' """
    if filters.get("company"):
            conditions += f""" AND tpr.company = '{filters["company"]}' """
    if filters.get("supplier"):
        conditions += f""" AND tpr.supplier = '{filters["supplier"]}' """
    if filters.get("state"):
        conditions += f""" AND addr.state = '{filters["state"]}' """
    if filters.get("available_in"):
        conditions += f""" AND addr.city = '{filters["available_in"]}' """
    if filters.get("purchase_category"):
        conditions += f""" AND tpr.custom_purchase_type = '{filters["purchase_category"]}' """
    if filters.get("current_status"):
        conditions += f""" AND tpr.status = '{filters["current_status"]}' """
    if filters.get("category"):
        conditions += f""" AND ti.ch_category = '{filters["category"]}' """
    if filters.get("ch_sub_category"):
        conditions += f""" AND ti.ch_sub_category = '{filters["ch_sub_category"]}' """
    if filters.get("brand"):
        conditions += f""" AND ti.brand = '{filters["brand"]}' """
    if filters.get("warehouse"):
        warehouse_list = "', '".join(filters.get("warehouse"))
        conditions += f""" AND tsn.warehouse IN ('{warehouse_list}') """

    return f"""
    SELECT tpr.name as pur_rec_no, ti.ch_category AS category,ti.ch_sub_category AS sub_category,ti.brand,ti.item_name AS item,tsn.name AS imei,
        tsn.warehouse ,tpr.supplier_name,tpr.custom_purchase_type AS purchase_category,
        tpri.rate AS per_cost,tpri.custom_exempted_value AS purchase_exempted,tpri.taxable_value AS purchase_taxable,
        tpri.cgst_rate,tpri.sgst_rate,tpri.igst_rate,
        tpri.cgst_amount,tpri.sgst_amount,tpri.igst_amount,
        tpr.status AS current_status,
        addr.city AS available_in,addr.state,
        tpr.posting_date,tpr.company ,tpr.tax_category,tptc.rate as tax_rate,tptc.tax_amount,
        tpo.name as order_id , tpi.name as invoice_id
    FROM `tabPurchase Receipt` tpr
    JOIN `tabPurchase Receipt Item` tpri ON tpri.parent = tpr.name
    JOIN `tabPurchase Taxes and Charges` tptc on tptc.parent = tpr.name
    JOIN `tabItem` ti ON ti.name = tpri.item_code 
    JOIN `tabSerial No` tsn ON tsn.purchase_document_no = tpr.name AND tsn.item_code = tpri.item_code
    JOIN `tabSupplier` ts ON ts.name = tpr.supplier
    LEFT JOIN `tabAddress` addr ON addr.address_title = ts.name
    LEFT JOIN `tabPurchase Order Item` tpoi  ON tpoi.name = tpri.purchase_order_item
    LEFT JOIN `tabPurchase Order` tpo ON tpo.name = tpoi.parent
    LEFT JOIN `tabPurchase Invoice Item` tpii ON tpii.purchase_receipt = tpr.name OR tpii.pr_detail = tpri.name
    LEFT JOIN `tabPurchase Invoice` tpi ON tpi.name = tpii.parent
    WHERE 1=1
    {conditions}
    """

@frappe.whitelist()
def download_report(filters=None):
    now = datetime.now()
    now_date = now.strftime("%d/%m/%Y %I:%M %p")
    today = date.today()
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("Purchase Report")
    user = frappe.session.user

    for row in range(5):
        worksheet.set_row(row, 25)

    title_format = workbook.add_format({'bold': True,'font_size': 12,'align': 'center','valign': 'vcenter','border':1}) #,'bg_color': '#000080','font_color': '#FFFFFF'
    data_format = workbook.add_format({'font_size': 12,'align': 'left','border':1}) 

    company_name = "BestBuy Mobiles Pvt Ltd"
    city = filters.get("available_in")
    state = filters.get("state")
    location_parts = []
    if city:
        location_parts.append(city)
    if state:
        location_parts.append(state)
    if location_parts:
        title_line = company_name + " - " + " - ".join(location_parts)
    else:
        title_line = company_name

    worksheet.merge_range('A1:Y1', "STOCK REPORT", title_format)
    worksheet.merge_range('A2:Y2', title_line, title_format)
    worksheet.merge_range('A3:Y3', f"Taken on {now_date} by user {user}", title_format)

    worksheet.merge_range('A4:H4', "Product Details", title_format)
    worksheet.merge_range('I4:U4', "Purchase Details", title_format)
    worksheet.merge_range('V4:Y4', "Status & Location Details", title_format)

    col_widths = [8,25,25,18, 25, 16, 45, 24, 20, 26, 20, 18, 25, 18, 16, 
                  16, 16, 16, 22, 60, 27, 30, 30, 45, 50]
    for i, width in enumerate(col_widths):
        worksheet.set_column(i, i, width)

    headers = ["S.No","Purchase Order ID","Purchase Invoice ID","Category", "Sub Category", "Brand", "Item", "IMEI", "Warehouse", "Supplier Name", 
        "Purchase Category", "Per Cost", "Purchase Exempted", "Purchase Taxable",
        "Tax Amount","Tax Rate", "Days Elapsed","Tax Category", "Current Status",
        "Intransit / Basket / Bin / Dispose Stock Days Elapsed", "Bin Name","Available In", "State",
        "Remarks Reasons Selection Type", "Remarks - Text comments"] 

    for col,headers in enumerate(headers):
        worksheet.write(4, col, headers,title_format)

    data = []
    result = frappe.db.sql(get_query(filters),as_dict =1)
    
    for i, row in enumerate(result,start=1):

        days_elapsed= (today - row.posting_date).days

        data.append([i,row.order_id,row.invoice_id, row.category, row.sub_category, row.brand, row.item, row.imei, row.warehouse,
            row.supplier_name, row.purchase_category, row.per_cost, row.purchase_exempted, row.purchase_taxable,
            row.tax_amount,f"{int(row.tax_rate)}%", days_elapsed,row.tax_category,
            row.current_status, "", row.pur_rec_no, row.available_in, row.state, "", ""])
        
    for row_idx, row_data in enumerate(data, start=5):
        worksheet.set_row(row_idx, 20)
        worksheet.write_row(row_idx, 0, row_data,data_format)

    workbook.close()
    output.seek(0)
    frappe.response['type'] = 'binary'
    frappe.response['filename'] = 'Purchase_Receipt_Report.xlsx'
    frappe.response['filecontent'] = output.getvalue()
import re

CSS_BLOCK = '''<style>
    /* ===== INVOICE PRINTER: Exact Reference Match ===== */
    @page { size: A4; margin: 0; }
    body { margin: 0; padding: 0; background: #fff; font-size: 11px; font-family: Arial, Helvetica, sans-serif; }

    .invoice-card {
        border: 1px solid #e0e0e0 !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        background: #ffffff !important;
        color: #333333 !important;
        font-family: Arial, Helvetica, sans-serif !important;
        font-size: 10px !important;
        line-height: 1.4 !important;
        max-width: 850px;
        margin: 0 auto 30px auto;
        page-break-inside: avoid;
    }

    .invoice-card .card-header {
        background: #ffffff !important;
        border-bottom: 0 !important;
        padding: 15px 15px 5px 15px !important;
    }

    .invoice-card .card-body {
        padding: 10px 15px !important;
    }

    /* Typography overrides */
    .invoice-card div, .invoice-card p, .invoice-card span {
        font-size: 11px !important;
        font-family: Arial, Helvetica, sans-serif !important;
        color: #333333 !important;
    }

    .invoice-card strong {
        font-size: 11px !important;
        font-weight: bold !important;
    }

    /* TAX INVOICE heading */
    .invoice-card h3 {
        font-size: 16px !important;
        font-weight: normal !important;
        margin: 0 !important;
        color: #333 !important;
        letter-spacing: 0.5px;
    }

    /* Items table - thin light-gray borders */
    .invoice-card .table-invoice {
        border-collapse: collapse !important;
        border-spacing: 0 !important;
        width: 100% !important;
        margin-bottom: 5px !important;
    }

    .invoice-card .table-invoice thead th {
        background: #fdfdfd !important;
        font-weight: bold !important;
        font-size: 11px !important;
        padding: 6px 4px !important;
        border: 1px solid #e0e0e0 !important;
        white-space: nowrap !important;
    }

    .invoice-card .table-invoice tbody td {
        font-size: 11px !important;
        padding: 5px 4px !important;
        border: 1px solid #e0e0e0 !important;
    }

    /* Grand total table */
    .invoice-card #invoice-grand-total-table {
        width: 100%;
        border-collapse: collapse !important;
    }

    .invoice-card #invoice-grand-total-table td {
        padding: 5px 4px !important;
        font-size: 11px !important;
        border: none !important;
        border-bottom: 1px solid #e0e0e0 !important;
    }
    
    .invoice-card #invoice-grand-total-table tr:last-child td {
        border-bottom: none !important;
    }

    /* Print overrides */
    @media print {
        .no-print { display: none !important; }
        .force-page-break { page-break-after: always; }
        .invoice-card { 
            border: none !important; /* Browsers sometimes double borders */
            margin-bottom: 2cm !important; 
        }
        body { padding: 1cm; }
    }
</style>'''

def get_block(is_credit_note, copy_type):
    title = "CREDIT NOTE" if is_credit_note else "TAX INVOICE"
    num_label = "Credit Note No" if is_credit_note else "Invoice No"
    num_var = "{{ credit_note.credit_note_number }}" if is_credit_note else "{{ invoice.invoice_number }}"
    date_label = "Credit Note Date" if is_credit_note else "Invoice Date"
    date_var = "{{ credit_note.credit_note_date }}" if is_credit_note else "{{ invoice.invoice_date }}"
    
    return f'''
<div class="invoice-card force-page-break">
    <!-- Header Section -->
    <div class="card-header border-bottom-0 d-block w-100">
        <div class="row align-items-start w-100 m-0">
            <!-- Logo -->
            <div class="col-4 text-left p-0">
                <img src="{{% static 'gstbillingapp/images/xlogo.jpeg' %}}" alt="Logo" style="max-width: 130px; margin-bottom: 15px;">
                <div style="font-size: 11px;">
                    <strong>{date_label}: {date_var}</strong>
                </div>
            </div>
            <!-- Title -->
            <div class="col-4 text-center p-0">
                <h3>{title}</h3>
                <div style="font-size: 10px; color: #555; margin-top: 2px;">({copy_type})</div>
            </div>
            <!-- Invoice Number -->
            <div class="col-4 text-right p-0" style="text-align: right;">
                <strong>{num_label}: XPL{num_var}</strong>
            </div>
        </div>
    </div>
    
    <!-- Divider -->
    <hr style="margin: 5px 0 10px 0; border-top: 1px solid #e0e0e0;">

    <!-- Seller / Buyer / Shipper Info -->
    <div class="card-body">
        <div class="row" style="margin-bottom: 10px;">
            <!-- Seller -->
            <div class="col-5">
                <div style="margin-bottom: 3px;"><strong>XPREDICT AUTOMATION SOLUTIONS PVT LTD</strong></div>
                <div style="margin-bottom: 2px;">Thimlapura Road, Hurulichikanahalli, Bengaluru - 560090</div>
                <div style="margin-bottom: 2px;">EMAIL: info@xpredictlabs.com</div>
                <div style="margin-bottom: 2px;">Phone: 9480269812</div>
                <div>GST No: 29AAACX2581L1ZU</div>
            </div>

            <!-- Billed To -->
            <div class="col-3">
                <div style="font-size:11px; margin-bottom:3px; color:#333;">Billed To:</div>
                <div style="margin-bottom: 3px;"><strong>{{{{ invoice_data.customer_name }}}}</strong></div>
                <div style="margin-bottom: 2px;">{{{{ invoice_data.customer_address }}}}</div>
                <div style="margin-bottom: 2px;">Phone: {{{{ invoice_data.customer_phone }}}}</div>
                <div style="margin-bottom: 2px;">GST No: {{{{ invoice_data.customer_gst }}}}</div>
                {{% if invoice_data.customer_pan %}}
                <div style="margin-bottom: 2px;">PAN NO: {{{{ invoice_data.customer_pan }}}}</div>
                {{% elif invoice_data.buyer_pan_number %}}
                <div style="margin-bottom: 2px;">PAN NO: {{{{ invoice_data.buyer_pan_number }}}}</div>
                {{% elif invoice_data.buyer_tin_number %}}
                <div style="margin-bottom: 2px;">PAN NO: {{{{ invoice_data.buyer_tin_number }}}}</div>
                {{% endif %}}
                {{% if invoice_data.vehicle_number %}}
                <div><strong>PO No:</strong> {{{{ invoice_data.vehicle_number }}}}</div>
                {{% endif %}}
            </div>

            <!-- Shipped To -->
            <div class="col-4">
                <div style="font-size:11px; margin-bottom:3px; color:#333;">Shipped To:</div>
                <div style="margin-bottom: 3px;"><strong>{{{{ invoice_data.shipping_name }}}}</strong></div>
                <div style="margin-bottom: 2px;">{{{{ invoice_data.shipping_address }}}}</div>
                <div style="margin-bottom: 2px;">Phone: {{{{ invoice_data.shipping_phone }}}}</div>
                <div style="margin-bottom: 2px;">GST No: {{{{ invoice_data.shipping_gst }}}}</div>
                {{% if invoice_data.shipping_tin_number %}}
                <div style="margin-bottom: 2px;">PAN NO: {{{{ invoice_data.shipping_tin_number }}}}</div>
                {{% endif %}}
            </div>
        </div>

        <!-- Table -->
        <table class="table-invoice">
            <thead>
                <tr>
                    <th class="text-center" style="width: 5%; text-align: center;">Sl No</th>
                    <th class="text-left" style="width: 35%; text-align: left;">Description of Goods/Services</th>
                    <th class="text-center" style="width: 10%; text-align: center;">HSN / SAC</th>
                    <th class="text-center" style="width: 5%; text-align: center;">Unit</th>
                    <th class="text-right" style="width: 5%; text-align: right;">Qty</th>
                    <th class="text-right" style="width: 10%; text-align: right;">Rate (₹)</th>
                    <th class="text-right" style="width: 10%; text-align: right;">Taxable Amount (₹)</th>
                    <th class="text-right" style="width: 5%; text-align: right;">GST (%)</th>
                    {{% if invoice_data.igstcheck %}}
                    <th class="text-right" style="width: 15%; text-align: right;">IGST (₹)</th>
                    {{% else %}}
                    {{% endif %}}
                    <th class="text-right" style="width: 15%; text-align: right;">Total Amount (₹)</th>
                </tr>
            </thead>
            <tbody>
                {{% for item in invoice_data.items %}}
                <tr>
                    <td class="text-center" style="text-align: center;">{{{{ forloop.counter }}}}</td>
                    <td class="text-left" style="text-align: left;">{{{{ item.invoice_product }}}}</td>
                    <td class="text-center" style="text-align: center;">{{{{ item.invoice_hsn }}}}</td>
                    <td class="text-center" style="text-align: center;">{{{{ item.invoice_unit }}}}</td>
                    <td class="text-right" style="text-align: right;">{{{{ item.invoice_qty }}}}</td>
                    <td class="text-right" style="text-align: right;">{{{{ item.invoice_rate_without_gst|floatformat:2 }}}}</td>
                    <td class="text-right" style="text-align: right;">{{{{ item.invoice_amt_without_gst|floatformat:2 }}}}</td>
                    <td class="text-right" style="text-align: right;">{{{{ item.invoice_gst_percentage }}}}</td>
                    {{% if invoice_data.igstcheck %}}
                    <td class="text-right" style="text-align: right;">{{{{ item.invoice_amt_igst|floatformat:2 }}}}</td>
                    {{% else %}}
                    {{% endif %}}
                    <td class="text-right" style="text-align: right;">{{{{ item.invoice_amt_with_gst|floatformat:2 }}}}</td>
                </tr>
                {{% endfor %}}
            </tbody>
        </table>

        <!-- Lower Section -->
        <div class="row pt-2">
            <!-- Bank Details -->
            <div class="col-6 text-left" style="text-align: left;">
                <div style="font-weight: bold; margin-bottom: 15px;">Company Bank Details</div>
                <div style="margin-bottom: 2px;"><strong>Account Holder Name: {{{{ bank_details.account_holder_name|default:"XPREDICT AUTOMATION SOLUTIONS PVT LTD" }}}}</strong></div>
                <div style="margin-bottom: 2px;"><strong>Bank Name: {{{{ bank_details.bank_name|default:"State Bank of India" }}}}</strong></div>
                <div style="margin-bottom: 2px;"><strong>Branch: {{{{ bank_details.branch_name|default:"MG ROAD, BENGALURU" }}}}</strong></div>
                <div style="margin-bottom: 2px;"><strong>Account No: {{{{ bank_details.account_number|default:"43942921501" }}}}</strong></div>
                <div><strong>IFSC Code: {{{{ bank_details.ifsc_code|default:"SBIN0040006" }}}}</strong></div>
            </div>

            <!-- Tax Summary & Signatures -->
            <div class="col-6">
                <table id="invoice-grand-total-table">
                    <tr>
                        <td style="text-align: right; font-weight:bold;">Total Taxable Amount:</td>
                        <td style="text-align: right; font-weight:bold; width:100px;">{{{{ currency }}}} {{{{invoice_data.invoice_total_amt_without_gst|floatformat:2}}}}</td>
                    </tr>
                    {{% if invoice_data.igstcheck %}}
                    <tr>
                        <td style="text-align: right; font-weight:bold;">IGST:18%</td>
                        <td style="text-align: right; font-weight:bold; width:100px;">{{{{ currency }}}} {{{{invoice_data.invoice_total_amt_igst|floatformat:2}}}}</td>
                    </tr>
                    {{% else %}}
                    <tr>
                        <td style="text-align: right; font-weight:bold;">CGST:9%</td>
                        <td style="text-align: right; font-weight:bold; width:100px;">{{{{ currency }}}} {{{{invoice_data.invoice_total_amt_cgst|floatformat:2}}}}</td>
                    </tr>
                    <tr>
                        <td style="text-align: right; font-weight:bold;">SGST:9%</td>
                        <td style="text-align: right; font-weight:bold; width:100px;">{{{{ currency }}}} {{{{invoice_data.invoice_total_amt_sgst|floatformat:2}}}}</td>
                    </tr>
                    {{% endif %}}
                    <tr>
                        <td style="text-align: right; font-weight:bold; border-bottom: none !important;">Invoice Total:</td>
                        <td style="text-align: right; font-weight:bold; width:100px; border-bottom: none !important;">{{{{ currency }}}} {{{{invoice_data.invoice_total_amt_with_gst|floatformat:2}}}}</td>
                    </tr>
                </table>
                
                <div style="text-align: right; font-weight: bold; margin-top: 5px;">
                    Invoice Total In Words: {{{{ total_in_words }}}} only.
                </div>
                
                <div style="text-align: right; font-weight: bold; margin-top: 15px;">
                    For Xpredict Automation Solutions Pvt Ltd<br><br><br><br>
                    Authorized Signatory<br>
                    <span style="font-weight:bold;">E. & O.E.</span>
                </div>
            </div>
        </div>
    </div>
</div>
'''

def rebuild_file(filepath, is_credit_note):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    start_idx = content.find('<style>')
    end_idx = content.find('<button onclick="printAllCopies()"')
    
    if start_idx == -1 or end_idx == -1:
        print(f"Could not find boundaries in {filepath}")
        return
        
    head = content[:start_idx]
    tail = content[end_idx:]
    
    b1 = get_block(is_credit_note, "ORIGINAL FOR RECIPIENT").replace('force-page-break', '')
    b2 = get_block(is_credit_note, "ORIGINAL FOR RECIPIENT")
    b3 = get_block(is_credit_note, "DUPLICATE FOR TRANSPORTER")
    b4 = get_block(is_credit_note, "TRIPLICATE FOR SUPPLIER")
    
    new_middle = f'''{CSS_BLOCK}

<!-- Screen View -->
{b1}

<!-- Print Section - Hidden on screen -->
<div id="print-section" style="display: none;">
    <!-- Original Copy for Print -->
    {b2}
    
    <!-- Duplicate Copy -->
    {b3}
    
    <!-- Triplicate Copy -->
    {b4}
</div>

'''
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(head + new_middle + tail)
    
    print(f"Rebuilt {filepath}")

rebuild_file(r'c:\Users\user\CRM-EXPENSE-REPORTS\templates\gstbillingapp\invoice_printer.html', False)
rebuild_file(r'c:\Users\user\CRM-EXPENSE-REPORTS\templates\gstbillingapp\credit_note_printer.html', True)

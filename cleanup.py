import re

def clean_html(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove .table and .table-bordered from invoice tables
    content = content.replace('class="table table-bordered table-invoice"', 'class="table-invoice"')
    content = content.replace('class="table" id="invoice-grand-total-table"', 'id="invoice-grand-total-table"')
    content = content.replace('class="table table-bordered"', 'class="table-invoice"')

    # Remove outer .card class from the main invoice wrapper
    content = content.replace('class="card invoice-card"', 'class="invoice-card"')
    
    # Replace Billed To / Shipped To h6 with div to avoid tabler h6 styles
    content = content.replace('<h6 class="mb-3">Billed To:</h6>', '<div style="font-size:12px; font-weight:bold; margin-bottom:8px;">Billed To:</div>')
    content = content.replace('<h6 class="mb-3">Shipped To:</h6>', '<div style="font-size:12px; font-weight:bold; margin-bottom:8px;">Shipped To:</div>')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

clean_html(r'c:\Users\user\CRM-EXPENSE-REPORTS\templates\gstbillingapp\invoice_printer.html')
clean_html(r'c:\Users\user\CRM-EXPENSE-REPORTS\templates\gstbillingapp\credit_note_printer.html')
print("Applied cleanups successfully!")

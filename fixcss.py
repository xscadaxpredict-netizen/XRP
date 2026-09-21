import re

def fix_css(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace .card.invoice-card with .invoice-card
    content = content.replace('.card.invoice-card', '.invoice-card')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

fix_css(r'c:\Users\user\CRM-EXPENSE-REPORTS\templates\gstbillingapp\invoice_printer.html')
fix_css(r'c:\Users\user\CRM-EXPENSE-REPORTS\templates\gstbillingapp\credit_note_printer.html')
print("Fixed CSS selectors!")

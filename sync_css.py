import re

with open(r'c:\Users\user\CRM-EXPENSE-REPORTS\templates\gstbillingapp\invoice_printer.html', 'r', encoding='utf-8') as f:
    inv = f.read()

m = re.search(r'(<style>.*?</style>)', inv, re.DOTALL)
new_css = m.group(1)

with open(r'c:\Users\user\CRM-EXPENSE-REPORTS\templates\gstbillingapp\credit_note_printer.html', 'r', encoding='utf-8') as f:
    cn = f.read()

cn = re.sub(r'<style>.*?</style>', new_css, cn, flags=re.DOTALL)

with open(r'c:\Users\user\CRM-EXPENSE-REPORTS\templates\gstbillingapp\credit_note_printer.html', 'w', encoding='utf-8') as f:
    f.write(cn)

print('Synced CSS to credit_note_printer')

import os
import re

template_dir = '/Users/shashank/Downloads/xshottest/xshot/xshot/gstbillingapp/templates/gstbillingapp/'

files_to_copy = {
    'invoices.html': 'credit_notes.html',
    'invoice_create.html': 'credit_note_create.html',
    'invoice_edit.html': 'credit_note_edit.html',
    'invoice_printer.html': 'credit_note_printer.html',
}

for src, dst in files_to_copy.items():
    src_path = os.path.join(template_dir, src)
    dst_path = os.path.join(template_dir, dst)
    
    with open(src_path, 'r') as f:
        content = f.read()
    
    # Replace occurrences in the content.
    # Be careful not to replace things like "invoice-number" which is the HTML name of the field that we reused in views.py, 
    # but wait, if we change them, we must change them in views.py too.
    # In views.py, I used: invoice_data["invoice-number"], invoice_data["invoice-date"], etc.
    # So I SHOULD NOT change the HTML element names.
    # I should only change the URLs and visual text.
    
    # URL tags: {% url 'invoice_create' %} -> {% url 'credit_note_create' %}
    content = content.replace("'invoice_create'", "'credit_note_create'")
    content = content.replace("'invoices'", "'credit_notes'")
    content = content.replace("'invoice_viewer'", "'credit_note_viewer'")
    content = content.replace("'invoice_delete'", "'credit_note_delete'")
    content = content.replace("'invoice_edit'", "'credit_note_edit'")
    
    # Text replacements
    content = content.replace("Invoice", "Credit Note")
    content = content.replace("INVOICE", "CREDIT NOTE")
    content = content.replace("invoices", "credit_notes")
    # To handle variable names like invoice.id -> credit_note.id
    content = content.replace("invoice.", "credit_note.")
    content = content.replace(" invoice ", " credit_note ")
    # For loops: {% for invoice in invoices %}
    content = content.replace("for invoice in credit_notes", "for credit_note in credit_notes")
    
    # For edit template
    # Wait, the views use `invoice_data` variable which is passed.
    
    with open(dst_path, 'w') as f:
        f.write(content)

print("Templates copied and modified.")

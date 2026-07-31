with open('/Users/shashank/Downloads/xshottest/xshot/xshot/gstbillingapp/views.py', 'a') as f:
    f.write('''\n\nfrom .models import CreditNote

@login_required
def credit_note_create(request):
    banks = BankDetails.objects.all()
    invoices_list = Invoice.objects.filter(user=request.user).order_by('-id')

    today = date.today()
    inyear = today.strftime("%y")
    inmonth = today.strftime("%m")

    user_profile = get_object_or_404(UserProfile, user=request.user)
    if not user_profile.business_title:
        from django.contrib import messages
        messages.error(request, "Please update your business title in your profile.")
        return redirect('user_profile')

    context = {
        "banks": banks,
        "invoices_list": invoices_list,
        "default_credit_note_number": CreditNote.objects.filter(user=request.user).aggregate(Max('credit_note_number'))['credit_note_number__max'],
        "default_credit_note_date": datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d'),
    }

    if not context["default_credit_note_number"]:
        invno = str(inyear) + str(inmonth) + str("001")
        context["default_credit_note_number"] = invno
    else:
        temp = str(context["default_credit_note_number"])
        if inyear != temp[:2] or inmonth != temp[2:4]:
            invno = str(inyear) + str(inmonth)
        else:
            context["default_credit_note_number"] += 1

    if request.method == "POST":
        invoice_data = request.POST

        validation_error = invoice_data_validator(invoice_data)
        if validation_error:
            context["error_message"] = validation_error
            return render(request, "gstbillingapp/credit_note_create.html", context)

        invoice_data_processed = invoice_data_processor(invoice_data)

        customer = Customer.objects.filter(
            user=request.user,
            customer_name=invoice_data["customer-name"],
            customer_address=invoice_data["customer-address"],
            customer_phone=invoice_data["customer-phone"],
            customer_gst=invoice_data["customer-gst"],
            customer_pan=invoice_data.get("buyer_pan_number", "")
        ).first()

        if not customer:
            customer = Customer(
                user=request.user,
                customer_name=invoice_data["customer-name"],
                customer_address=invoice_data["customer-address"],
                customer_phone=invoice_data["customer-phone"],
                customer_gst=invoice_data["customer-gst"],
                customer_pan=invoice_data.get("buyer_pan_number", ""),
            )
            customer.save()

        bank_id = invoice_data.get("bank_id")
        bank = None
        if bank_id:
            try:
                bank = BankDetails.objects.get(id=bank_id)
            except BankDetails.DoesNotExist:
                bank = None  

        associated_invoice_id = invoice_data.get("associated_invoice_id")
        associated_invoice = None
        if associated_invoice_id:
            try:
                associated_invoice = Invoice.objects.get(id=associated_invoice_id, user=request.user)
            except Invoice.DoesNotExist:
                pass

        update_products_from_invoice(invoice_data_processed, request)

        invoice_data_processed_json = json.dumps(invoice_data_processed)
        temp = json.loads(invoice_data_processed_json)

        new_cn = CreditNote(
            user=request.user,
            credit_note_number=int(invoice_data["invoice-number"]), 
            credit_note_date=datetime.datetime.strptime(invoice_data["invoice-date"], "%Y-%m-%d"),
            associated_invoice=associated_invoice,
            bank=bank,
            credit_note_customer=customer,
            credit_note_json=invoice_data_processed_json,
            credit_note_customer_gst=invoice_data["customer-gst"],
            credit_note_customer_phone=invoice_data["customer-phone"],
            credit_note_amt_without_gst=temp["invoice_total_amt_without_gst"],
            credit_note_amt_igst=temp["invoice_total_amt_igst"],
            credit_note_amt_cgst=temp["invoice_total_amt_cgst"],
            credit_note_amt_sgst=temp["invoice_total_amt_sgst"],
            credit_note_amt_with_gst=temp["invoice_total_amt_with_gst"],
            business_tin_number=invoice_data.get("supplier_tin_number", ""),
            buyer_tin_number=invoice_data.get("buyer_tin_number", ""),
            terms_and_conditions=invoice_data.get("terms_and_conditions", ""),
            sup_pan_number=invoice_data.get("sup_pan_number", ""),
            project_description=invoice_data.get("project_description", ""),
        )
        
        new_cn.save()

        return redirect("credit_note_viewer", credit_note_id=new_cn.id)

    return render(request, "gstbillingapp/credit_note_create.html", context)

@login_required
def credit_notes(request):
    if request.user.is_superuser or request.user.is_staff:
        cn_qs = CreditNote.objects.all().order_by('-id')
    else:
        cn_qs = CreditNote.objects.filter(user=request.user).order_by('-id')

    context = {
        "credit_notes": cn_qs
    }
    return render(request, "gstbillingapp/credit_notes.html", context)

@login_required
def credit_note_viewer(request, credit_note_id):
    if request.user.is_staff or request.user.is_superuser:
        cn_obj = get_object_or_404(CreditNote, id=credit_note_id)
    else:
        cn_obj = get_object_or_404(CreditNote, user=request.user, id=credit_note_id)

    user_profile = get_object_or_404(UserProfile, user=request.user)
    cn_json = json.loads(cn_obj.credit_note_json)

    if "project_description" not in cn_json and hasattr(cn_obj, "project_description"):
        cn_json["project_description"] = cn_obj.project_description

    context = {
        "invoice": cn_obj, 
        "credit_note": cn_obj,
        "invoice_data": cn_json,
        "currency": "₹",
        "total_in_words": num2words.num2words(
            int(cn_json["invoice_total_amt_with_gst"]),
            lang="en_IN"
        ).title(),
        "user_profile": user_profile,
        "bank_details": cn_obj.bank,
        "sup_pan_number": getattr(cn_obj, "sup_pan_number", None),
    }

    return render(request, "gstbillingapp/credit_note_printer.html", context)

@login_required
def credit_note_delete(request):
    if request.method == "POST":
        cn_id = request.POST["credit_note_id"]
        cn_obj = get_object_or_404(CreditNote, user=request.user, id=cn_id)
        cn_obj.delete()
    return redirect("credit_notes")

@login_required
def credit_note_edit(request, credit_note_id):
    cn = get_object_or_404(CreditNote, id=credit_note_id)

    if not request.user.is_superuser and cn.user != request.user:
        return HttpResponseForbidden("Not allowed")

    banks = BankDetails.objects.all()
    invoices_list = Invoice.objects.filter(user=request.user).order_by("-id")

    existing_data = json.loads(cn.credit_note_json)
    
    if "project_description" not in existing_data and hasattr(cn, "project_description"):
        existing_data["project_description"] = cn.project_description

    if request.method == "POST":
        invoice_data_processed = invoice_data_processor(request.POST)

        update_products_from_invoice(invoice_data_processed, request)

        cn.credit_note_json = json.dumps(invoice_data_processed)

        temp = invoice_data_processed

        cn.credit_note_number = int(request.POST["invoice-number"])
        cn.credit_note_date = request.POST["invoice-date"]
        cn.credit_note_amt_without_gst = temp["invoice_total_amt_without_gst"]
        cn.credit_note_amt_igst = temp["invoice_total_amt_igst"]
        cn.credit_note_amt_cgst = temp["invoice_total_amt_cgst"]
        cn.credit_note_amt_sgst = temp["invoice_total_amt_sgst"]
        cn.credit_note_amt_with_gst = temp["invoice_total_amt_with_gst"]
        
        bank_id = request.POST.get("bank_id")
        if bank_id:
            cn.bank = BankDetails.objects.get(id=bank_id)

        associated_invoice_id = request.POST.get("associated_invoice_id")
        if associated_invoice_id:
            try:
                cn.associated_invoice = Invoice.objects.get(id=associated_invoice_id, user=request.user)
            except Invoice.DoesNotExist:
                cn.associated_invoice = None
        else:
            cn.associated_invoice = None

        cn.project_description = request.POST.get("project_description", "")

        cn.save()

        return redirect("credit_note_viewer", credit_note_id=cn.id)

    context = {
        "invoice": cn,
        "credit_note": cn,
        "banks": banks,
        "invoices_list": invoices_list,
        "invoice_data": existing_data,
    }

    return render(request, "gstbillingapp/credit_note_edit.html", context)
''')

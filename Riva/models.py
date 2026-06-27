from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Products(models.Model):
    name = models.CharField(max_length=100)
    hsncode=models.CharField(max_length=30, default='')
    base_amount=models.DecimalField(max_digits=20, decimal_places=2, default=0)
    gst=models.DecimalField(max_digits=20, decimal_places=2, default=0)

    def __str__(self):  # Correct method name
        return self.name

class Executive(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    
class FileUploadModel(models.Model):
    file = models.FileField(upload_to='uploads/')
    name = models.CharField(max_length=255)  # Optional: To store a custom file name
    # Other metadata you might want for the files can go here

    def __str__(self):
        return self.name 
# In models.py
class Enquiry(models.Model):
    STATUS_CHOICES = [
        ('1', 'HOT'),
        ('2', 'WARM'),
        ('3', 'COLD'),
    ]
  
    companyname = models.CharField(max_length=255, default='', blank=True, null=True)
    customername = models.CharField(max_length=20, default='', blank=True, null=True)
    
    refrence = models.CharField(max_length=20, default='',blank=True)
    email = models.EmailField( null=True, blank=True)
    contact = models.IntegerField( blank=True, null=True)
    location = models.CharField(max_length=100, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='')
    products = models.ForeignKey(Products, on_delete=models.CASCADE, default=1)  # Make sure product with id=1 exists
    subproduct = models.CharField(max_length=20, default='',blank=True)
    closuredate = models.DateField(null=True, blank=True)
    executive = models.ForeignKey(Executive, on_delete=models.CASCADE,  blank=True, null=True)
    files = models.ManyToManyField(FileUploadModel, blank=True)
    remarks = models.TextField(max_length=255, default='', blank=True)
    flag = models.TextField(max_length=200, default='', blank=True)
    enqtype = models.CharField(max_length=20, default='',blank=True)
    is_confirmed = models.BooleanField(default=False) 
    created_at = models.DateTimeField(auto_now_add=True)
    is_lost = models.BooleanField(default=False)
    is_reverted = models.BooleanField(default=False) 
    is_relegated=models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True) 
    
    def __str__(self):
        return f"Enquiry from {self.companyname}"

    
class RevertRemark(models.Model):
    enquiry = models.ForeignKey(Enquiry, related_name='revert_remarks', on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Remark for {self.enquiry.companyname} - {self.created_at}"
    

class quotation(models.Model):
    qid= models.ForeignKey(Enquiry, on_delete=models.CASCADE)
    quote=models.FileField(upload_to='quotes/', blank=True, null=True)
    baseamount=models.DecimalField(max_digits=15, decimal_places=2, default=0)
    boq=models.FileField(upload_to='boqs/', blank=True, null=True)
    finalamount=models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE,null=True, blank=True) 
    
 
    def __str__(self):
        return f"Quotation for {self.qid}"

from datetime import timedelta

class FollowUp(models.Model):
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="followups")
    foname = models.CharField(max_length=255)
    fodate = models.DateField()
    fotime = models.TimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Calculate the notification date as one day prior to the fodate
        self.notify_on = self.fodate - timedelta(days=1)
        super().save(*args, **kwargs)



class ConfirmedOrder(models.Model):
    quotation = models.ForeignKey(quotation, on_delete=models.CASCADE)
    project_closing_date = models.DateField()
    workorder = models.FileField(upload_to='workorders/', blank=True, null=True)
    boq = models.FileField(upload_to='boqs/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE,null=True, blank=True) 
    
    # Make 'enquiry' nullable for existing rows
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Confirmed Order for Enquiry #{self.enquiry.id if self.enquiry else 'No Enquiry'}"

from django import forms
class ConfirmedOrderForm(forms.ModelForm):
    class Meta:
        model = ConfirmedOrder
        fields = ['quotation', 'project_closing_date', 'workorder', 'boq']
        widgets = {
            'project_closing_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super(ConfirmedOrderForm, self).__init__(*args, **kwargs)
        self.fields['quotation'].queryset = quotation.objects.all() 


class confirmed_enquiry(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE,null=True, blank=True) 
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, null=True, blank=True)
    quotation=models.CharField(max_length=40 )
    revert = models.BooleanField(default=False)
    relegate=models.BooleanField(default=False)

class ConfirmedOrderFollowUp(models.Model):
    confirmed_order = models.ForeignKey(
        confirmed_enquiry,
        
        on_delete=models.CASCADE,
        related_name='followups',
        help_text="The confirmed order associated with this follow-up"
    )
    foname = models.CharField(max_length=20, default='', help_text="Name associated with the follow-up")
    fodate = models.DateField(help_text="Date of the follow-up")
    fotime = models.TimeField(help_text="Time of the follow-up")
    entrydate = models.DateTimeField(default=timezone.now, help_text="Timestamp for when this entry was created or modified")

    def __str__(self):
        return f"Follow-up by {self.foname} on {self.fodate} at {self.fotime}"
    


class Xpredict(models.Model):
    company_name = models.CharField(max_length=255)
    phone_no = models.CharField(max_length=15)
    mail = models.EmailField()
    gst = models.CharField(max_length=15, blank=True, null=True)
    pan = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField()
    terms_conditions = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.company_name
    

class BankDetails(models.Model):
    bank_name = models.CharField(max_length=255)
    account_holder_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    branch_name = models.CharField(max_length=255)
    address = models.TextField()
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"
    



from django.db import models

class CommercialQuote(models.Model):
    enquiry_id = models.CharField(max_length=50)
    quotation_no = models.CharField(max_length=50)
    
    # Bill To Fields
    bill_to_company_name = models.CharField(max_length=255)
    bill_to_customer_name = models.CharField(max_length=255)
    bill_to_gst_number = models.CharField(max_length=20)
    bill_to_address = models.TextField()

    # Ship To Fields
    ship_to_company_name = models.CharField(max_length=255)
    ship_to_customer_name = models.CharField(max_length=255)
    ship_to_gst_number = models.CharField(max_length=20)
    ship_to_address = models.TextField()

    # From Details
    from_company_name = models.CharField(max_length=255)
    from_phone = models.CharField(max_length=15)
    from_email = models.EmailField()
    from_gst = models.CharField(max_length=20)
    from_pan = models.CharField(max_length=20)
    from_address = models.TextField()

    # Bank Details (ForeignKey to BankDetails model)
    bank = models.ForeignKey('BankDetails', on_delete=models.CASCADE)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cgst_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sgst_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    igst_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    dealer_margin = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    terms_and_conditions = models.TextField()



    def __str__(self):
        return f"Quote {self.quotation_no} for Enquiry {self.enquiry_id}"



class QuotationItem(models.Model):
    quotation_no = models.CharField(max_length=50 , default=0)  # Replaced ForeignKey with quotation_no (link to CommercialQuote)
    product = models.ForeignKey('Products', on_delete=models.CASCADE)
    hsncode = models.CharField(max_length=30, default='')
    base_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField()
    margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    rate = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    transfer_price = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    dealer_margin = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} x {self.rate}"




# techno commercial ########################################################################

class QuotationProduct(models.Model):
    pd_name = models.CharField(max_length=100)

    def __str__(self):  
        return self.pd_name


class QProduct(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    observation = models.TextField()
    suggestion = models.TextField()
    proposal = models.TextField()
    feat_advantages = models.TextField()
    salient_feat = models.TextField()
    dristi_subscription = models.TextField()
    iot_hardware = models.TextField()


class Table1(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    sl_no = models.IntegerField()
    raw_sewage_characteristics = models.CharField(max_length=100)
    unit = models.CharField(max_length=100)
    value = models.CharField(max_length=50)


class StandardTable(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    sl_no = models.IntegerField()
    principal_purpose_unit_process = models.CharField(max_length=1000)
    unit_processes = models.CharField(max_length=1000)


class SiteInfo(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    info_text = models.TextField()
    standard_text = models.TextField()
    table1 = models.ForeignKey(Table1, on_delete=models.CASCADE)
    standard_table = models.ForeignKey(StandardTable, on_delete=models.CASCADE)


class SpecTable(models.Model):
    sl_no = models.IntegerField()
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    specs_for_25kld = models.CharField(max_length=1000)
    hidrec = models.CharField(max_length=1000)


class ReqSpecification(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    req_text = models.TextField()
    specs_table = models.ForeignKey(SpecTable, on_delete=models.CASCADE)
    process_diagram_text = models.CharField(max_length=1000)
    process_diagram1 = models.FileField(upload_to='process_diagrams/')
    process_diagram2 = models.FileField(upload_to='process_diagrams/')


class OutputTable(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    sl_no = models.IntegerField()
    treated_water_characteristics = models.CharField(max_length=2000)
    unit = models.CharField(max_length=100)
    standard_value = models.CharField(max_length=100)


class ProcessDescription(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    process_description_text = models.TextField()
    etp_text = models.TextField()
    stp_text = models.TextField()
    shs_text = models.TextField()
    automation_text = models.TextField()
    footprint_area = models.TextField()
    tentative_BOM = models.TextField()
    output_table = models.ForeignKey(OutputTable, on_delete=models.CASCADE)


class InstallationTable(models.Model):
    sl_no = models.IntegerField()
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    capacity = models.CharField(max_length=100)
    total_needed_capacity = models.CharField(max_length=100)
    waste_water_type = models.CharField(max_length=100)
    total_no_machines = models.CharField(max_length=100)


class SpecificationTable(models.Model):
    sl_no = models.IntegerField()
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)   
    specification = models.CharField(max_length=1000)
    qnty = models.IntegerField()
    unit = models.CharField(max_length=50)
    unit_rate = models.DecimalField(max_digits=10, decimal_places=2)
    price_exgst = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=15, decimal_places=2)


class OptionalHardwareTable(models.Model):
    sl_no = models.IntegerField()
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)   
    optional_hardware = models.CharField(max_length=2000)
    qnty = models.IntegerField()
    unit = models.CharField(max_length=50)
    unit_rate = models.DecimalField(max_digits=10, decimal_places=2)
    price_exgst = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=15, decimal_places=2)


class Pricing(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    machine_cost_text = models.TextField()
    installation_table = models.ForeignKey(InstallationTable, on_delete=models.CASCADE)
    specification_table = models.ForeignKey(SpecificationTable, on_delete=models.CASCADE)
    optional_hardware_table = models.ForeignKey(OptionalHardwareTable, on_delete=models.CASCADE)
    terms_conditions = models.TextField()


class GeneralTermsAndConditions(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    performance = models.CharField(max_length=1000)
    flow_characteristics = models.CharField(max_length=1000)
    trial_quality_check = models.TextField()
    virtual_completion = models.TextField()
    limitation_liability = models.CharField(max_length=1000)
    force_clause = models.CharField(max_length=1000)
    additional_works = models.CharField(max_length=1000)
    warranty_guaranty = models.TextField()
    arbitration = models.CharField(max_length=1000)
    validity = models.CharField(max_length=1000)


class Appendix(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    installation_table = models.ForeignKey(InstallationTable, on_delete=models.CASCADE)
    supply_eq = models.TextField()
    instal_commissioning = models.TextField()
    clients_scope = models.TextField()
    note = models.CharField(max_length=100)


class Contents(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    contents = models.TextField()

class ContentsPR(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    contents = models.TextField()


class Proposal(models.Model):
    installation_table = models.ForeignKey(InstallationTable, on_delete=models.CASCADE)
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)


class Inclusions(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE)
    maintenance = models.TextField()
    yearly_maintenance = models.TextField()
    running_consumables = models.TextField()
    exclusions = models.TextField()


class ParticularsTable(models.Model):
    sl_no = models.IntegerField()
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE) 
    particulars = models.CharField(max_length=2000)
    first_year_exgst = models.DecimalField(max_digits=10, decimal_places=2)


class AMC_Pricing(models.Model):
    pd_name = models.ForeignKey(QuotationProduct, on_delete=models.CASCADE) 
    installation_table = models.ForeignKey(InstallationTable, on_delete=models.CASCADE)
    particulars_table = models.ForeignKey(ParticularsTable, on_delete=models.CASCADE)
    terms_conditions = models.TextField(null=True)

from django.db import models

class KeyValueStore(models.Model):
    key = models.CharField(max_length=255, unique=True)
    value = models.TextField()

    def __str__(self):
        return f"{self.key}: {self.value}"

class companydetails(models.Model):
    c_name=models.CharField(max_length=200)
    mail=models.EmailField()
    phone=models.CharField(max_length=20)




class Hidrec_wash(models.Model):
    
    contents=models.TextField()
    hidrec_wash_text=models.TextField()
    price=models.CharField(max_length=100,blank=True,null=True)
    carwash_text=models.TextField()
    priceoil_skimmer=models.CharField(max_length=100,blank=True,null=True)
    specification=models.TextField()
    terms_conditions=models.TextField()
    general_maintenance=models.TextField()
    total_price=models.CharField(max_length=100,blank=True,null=True)

class ConfirmedHidrecWash(models.Model):
    enquiry_id = models.IntegerField()
    quotation_no=models.CharField( max_length=50, blank=True, null=True)
    contents = models.TextField()
    hidrec_wash_text = models.TextField()
    price = models.CharField(max_length=100, blank=True, null=True)
    carwash_text = models.TextField()
    priceoil_skimmer = models.CharField(max_length=100, blank=True, null=True)
    specification = models.TextField()
    terms_conditions = models.TextField()
    general_maintenance = models.TextField()
    total_price = models.CharField(max_length=100, blank=True, null=True)

class Dealership(models.Model):
    name = models.CharField(max_length=255)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    target_orders = models.IntegerField(default=0)
    target_revenue = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    members = models.ManyToManyField(User, blank=True, related_name='dealerships')

    def __str__(self):
        return self.name

class DealershipPricing(models.Model):
    dealership = models.ForeignKey(Dealership, on_delete=models.CASCADE, related_name='product_pricing')
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    transfer_price = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    max_price = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ('dealership', 'product')

    def __str__(self):
        return f"{self.dealership.name} - {self.product.name} Pricing"


class UploadedQuote(models.Model):
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='uploaded_quotes')
    quote_type = models.CharField(max_length=100) # 'Commercial', 'Techno AMC', 'Hidrewash'
    file = models.FileField(upload_to='uploaded_quotes/')
    quotation_no = models.CharField(max_length=100, unique=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.quote_type} - {self.quotation_no}"

from django.contrib import admin
from Riva.models import UploadedQuote,Enquiry ,Products ,Hidrec_wash ,ConfirmedHidrecWash, Executive,quotation,ConfirmedOrder,FollowUp,ConfirmedOrderFollowUp, Xpredict,BankDetails,CommercialQuote, QuotationItem,companydetails,confirmed_enquiry,RevertRemark, Dealership, DealershipPricing
# Register your models here.
admin.site.register(Hidrec_wash)
admin.site.register(ConfirmedHidrecWash)
admin.site.register(Enquiry)
admin.site.register(Products)
admin.site.register(Executive)
admin.site.register(quotation)
admin.site.register(ConfirmedOrder)
admin.site.register(FollowUp)
admin.site.register(ConfirmedOrderFollowUp)
admin.site.register( Xpredict)
admin.site.register(BankDetails)
admin.site.register(CommercialQuote)
admin.site.register( QuotationItem)
admin.site.register(companydetails)
admin.site.register(confirmed_enquiry)
admin.site.register(RevertRemark)

from .models import (
    QuotationProduct,
    QProduct,
    Table1,
    StandardTable,
    SiteInfo,
    SpecTable,
    ReqSpecification,
    OutputTable,
    ProcessDescription,
    InstallationTable,
    SpecificationTable,
    OptionalHardwareTable,
    Pricing,
    GeneralTermsAndConditions,
    Appendix,
    Contents,
    ContentsPR,
    Proposal,
    Inclusions,
    ParticularsTable,
    AMC_Pricing,
    KeyValueStore,
)

# Register models to make them accessible in the Django admin
admin.site.register(QuotationProduct)
admin.site.register(UploadedQuote)
admin.site.register(QProduct)
admin.site.register(Table1)
admin.site.register(StandardTable)
admin.site.register(SiteInfo)
admin.site.register(SpecTable)
admin.site.register(ReqSpecification)
admin.site.register(OutputTable)
admin.site.register(ProcessDescription)
admin.site.register(InstallationTable)
admin.site.register(SpecificationTable)
admin.site.register(OptionalHardwareTable)
admin.site.register(Pricing)
admin.site.register(GeneralTermsAndConditions)
admin.site.register(Appendix)
admin.site.register(Contents)
admin.site.register(ContentsPR)
admin.site.register(Proposal)
admin.site.register(Inclusions)
admin.site.register(ParticularsTable)
admin.site.register(AMC_Pricing)
admin.site.register(KeyValueStore)
admin.site.register(Dealership)
admin.site.register(DealershipPricing)

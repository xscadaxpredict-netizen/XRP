from django.contrib import admin
from .models import  FCMToken,MobileSession,DirectPay,Conveyance,AdvanceGroupUpdateLog,AdvanceGroup,AdvanceAssignment, Expense, CashVoucher, Notification, Payment, BorrowedAmount,AdvancePayment, PaymentRequest, PaymentRequestMessage,ProofPhoto, GlobalSettings

# Register the Expense model
admin.site.register(FCMToken)
admin.site.register(Expense)

admin.site.register(Notification)
admin.site.register(MobileSession)
admin.site.register(AdvancePayment)
admin.site.register(ProofPhoto)
admin.site.register(AdvanceGroupUpdateLog)
admin.site.register(AdvanceGroup)
admin.site.register(AdvanceAssignment)
admin.site.register(PaymentRequest)
admin.site.register(PaymentRequestMessage)
admin.site.register(DirectPay)
admin.site.register(GlobalSettings)
from .models import Holiday, AdvanceAdjustment
admin.site.register(Holiday)
admin.site.register(AdvanceAdjustment)

from django.contrib import admin
from .models import Conveyance, ConveyanceSite

@admin.register(Conveyance)
class ConveyanceAdmin(admin.ModelAdmin):
    list_display = ('vehicle_type', 'price_per_km')

@admin.register(ConveyanceSite)
class ConveyanceSiteAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'kilometers')

# Register the CashVoucher model
admin.site.register(CashVoucher)

# Admin configuration for Payment
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('paid_to', 'transaction_id', 'amount', 'from_date', 'to_date', 'created_at')
    search_fields = ('transaction_id', 'user__username')
    list_filter = ('from_date', 'to_date', 'created_at')

# Admin configuration for BorrowedAmount
@admin.register(BorrowedAmount)
class BorrowedAmountAdmin(admin.ModelAdmin):
    list_display = ('expense', 'borrowed_from', 'amount')
    search_fields = ('expense__item_name', 'borrowed_from__username')
    list_filter = ('expense__transaction_date',)

# from django.contrib import admin
# from .models import Expense

# class ExpenseAdmin(admin.ModelAdmin):
#     list_display = ('item_name', 'amount', 'transaction_category', 'borrowed_amount', 'borrowed_from', 'status')
#     list_filter = ('transaction_category', 'status', 'created_by')
#     search_fields = ('item_name', 'transaction_details')

# # Register the model with the customized admin class
# admin.site.register( ExpenseAdmin)

import datetime
import json

from django.db.models import Sum


from .models import Product



def invoice_data_validator(invoice_data):
    
    # Validate Invoice Info ----------

    # invoice-number
    try:
        invoice_number = int(invoice_data['invoice-number'])
    except:
        print("Error: Incorrect Invoice Number")
        return "Error: Incorrect Invoice Number"

    # invoice date
    try:
        date_text = invoice_data['invoice-date']
        datetime.datetime.strptime(date_text, '%Y-%m-%d')
    except:
        print("Error: Incorrect Invoice Date")
        return "Error: Incorrect Invoice Date"

    # Validate Customer Data ---------

    # customer-name
    if len(invoice_data['customer-name']) < 1 or len(invoice_data['customer-name']) > 200:
        print("Error: Incorrect Customer Name")
        return "Error: Incorrect Customer Name"

    if len(invoice_data['customer-address']) > 600:
        print("Error: Incorrect Customer Address")
        return "Error: Incorrect Customer Address"

    if len(invoice_data['customer-phone']) > 14:
        print("Error: Incorrect Customer Phone")
        return "Error: Incorrect Customer Phone"
    if len(invoice_data['customer-gst']) != 15 and len(invoice_data['customer-gst']) != 0:
        print("Error: Incorrect Customer GST")
        return "Error: Incorrect Customer GST"
    return None


def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == '':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_val(data, key, default=''):
    if hasattr(data, 'getlist'):
        vals = data.getlist(key)
        return vals[0] if vals else default
    val = data.get(key, default)
    if isinstance(val, list):
        return val[0] if val else default
    return val if val is not None else default


def safe_list(data, key):
    if hasattr(data, 'getlist'):
        return data.getlist(key)
    val = data.get(key, [])
    if isinstance(val, list):
        return val
    if val is None or str(val).strip() == '':
        return []
    return [val]


def invoice_data_processor(invoice_post_data):
    print(invoice_post_data)
    processed_invoice_data = {}

    # Invoice Details
    processed_invoice_data['invoice_number'] = safe_val(invoice_post_data, 'invoice-number')
    processed_invoice_data['invoice_date'] = safe_val(invoice_post_data, 'invoice-date')

    # Billing (Customer) Details
    processed_invoice_data['customer_name'] = safe_val(invoice_post_data, 'customer-name')
    processed_invoice_data['customer_address'] = safe_val(invoice_post_data, 'customer-address')
    processed_invoice_data['customer_phone'] = safe_val(invoice_post_data, 'customer-phone')
    processed_invoice_data['customer_gst'] = safe_val(invoice_post_data, 'customer-gst')
    processed_invoice_data['customer_pan'] = safe_val(invoice_post_data, 'buyer_pan_number')
    processed_invoice_data['buyer_pan_number'] = safe_val(invoice_post_data, 'buyer_pan_number')

    # Shipping Details
    if 'same-as-billing-checkbox' in invoice_post_data:
        # If checkbox is checked, use billing info as shipping info
        processed_invoice_data['shipping_name'] = processed_invoice_data['customer_name']
        processed_invoice_data['shipping_address'] = processed_invoice_data['customer_address']
        processed_invoice_data['shipping_phone'] = processed_invoice_data['customer_phone']
        processed_invoice_data['shipping_gst'] = processed_invoice_data['customer_gst']
        processed_invoice_data['shipping_pan'] = processed_invoice_data['customer_pan']
        processed_invoice_data['shipping_tin_number'] = safe_val(invoice_post_data, 'buyer_tin_number')
    else:
        # If checkbox not checked, use separate shipping info
        processed_invoice_data['shipping_name'] = safe_val(invoice_post_data, 'shipping-name')
        processed_invoice_data['shipping_address'] = safe_val(invoice_post_data, 'shipping-address')
        processed_invoice_data['shipping_phone'] = safe_val(invoice_post_data, 'shipping-phone')
        processed_invoice_data['shipping_gst'] = safe_val(invoice_post_data, 'shipping-gst')
        processed_invoice_data['shipping_tin_number'] = safe_val(invoice_post_data, 'shipping_tin_number')

    # Other Invoice Fields
    manual_po = safe_val(invoice_post_data, "vehicle-number")
    dropdown_po = safe_val(invoice_post_data, "vehicle-number-dropdown")

    processed_invoice_data["vehicle_number"] = (
        manual_po.strip()
        if manual_po and manual_po.strip()
        else (dropdown_po.strip() if dropdown_po else "")
    )
    processed_invoice_data['business_tin_number'] = safe_val(invoice_post_data, 'supplier_tin_number')
    processed_invoice_data['buyer_tin_number'] = safe_val(invoice_post_data, 'buyer_tin_number')
    processed_invoice_data['terms_and_conditions'] = safe_val(invoice_post_data, 'terms_and_conditions')
    processed_invoice_data['sup_pan_number'] = safe_val(invoice_post_data, 'sup_pan_number')
    processed_invoice_data['project_description'] = safe_val(invoice_post_data, 'project_description')

    # IGST Checkbox
    processed_invoice_data['igstcheck'] = 'igstcheck' in invoice_post_data

    # Totals
    processed_invoice_data['invoice_total_amt_without_gst'] = safe_float(safe_val(invoice_post_data, 'invoice-total-amt-without-gst'))
    processed_invoice_data['invoice_total_amt_sgst'] = safe_float(safe_val(invoice_post_data, 'invoice-total-amt-sgst'))
    processed_invoice_data['invoice_total_amt_cgst'] = safe_float(safe_val(invoice_post_data, 'invoice-total-amt-cgst'))
    processed_invoice_data['invoice_total_amt_igst'] = safe_float(safe_val(invoice_post_data, 'invoice-total-amt-igst'))
    processed_invoice_data['invoice_total_amt_with_gst'] = safe_float(safe_val(invoice_post_data, 'invoice-total-amt-with-gst'))

    # Line Items
    processed_invoice_data['items'] = []

    products = safe_list(invoice_post_data, 'invoice-product')
    hsn_list = safe_list(invoice_post_data, 'invoice-hsn')
    unit_list = safe_list(invoice_post_data, 'invoice-unit')
    qty_list = safe_list(invoice_post_data, 'invoice-qty')
    rate_with_gst_list = safe_list(invoice_post_data, 'invoice-rate-with-gst')
    gst_pct_list = safe_list(invoice_post_data, 'invoice-gst-percentage')
    rate_without_gst_list = safe_list(invoice_post_data, 'invoice-rate-without-gst')
    amt_without_gst_list = safe_list(invoice_post_data, 'invoice-amt-without-gst')
    amt_sgst_list = safe_list(invoice_post_data, 'invoice-amt-sgst')
    amt_cgst_list = safe_list(invoice_post_data, 'invoice-amt-cgst')
    amt_igst_list = safe_list(invoice_post_data, 'invoice-amt-igst')
    amt_with_gst_list = safe_list(invoice_post_data, 'invoice-amt-with-gst')

    for idx, product in enumerate(products):
        if product and str(product).strip():
            def get_item_val(lst, default=''):
                return lst[idx] if idx < len(lst) else default

            item_entry = {
                'invoice_product': product,
                'invoice_hsn': get_item_val(hsn_list, ''),
                'invoice_unit': get_item_val(unit_list, ''),
                'invoice_qty': safe_float(get_item_val(qty_list, 0.0)),
                'invoice_rate_with_gst': safe_float(get_item_val(rate_with_gst_list, 0.0)),
                'invoice_gst_percentage': safe_float(get_item_val(gst_pct_list, 0.0)),
                'invoice_rate_without_gst': safe_float(get_item_val(rate_without_gst_list, 0.0)),
                'invoice_amt_without_gst': safe_float(get_item_val(amt_without_gst_list, 0.0)),
                'invoice_amt_sgst': safe_float(get_item_val(amt_sgst_list, 0.0)),
                'invoice_amt_cgst': safe_float(get_item_val(amt_cgst_list, 0.0)),
                'invoice_amt_igst': safe_float(get_item_val(amt_igst_list, 0.0)),
                'invoice_amt_with_gst': safe_float(get_item_val(amt_with_gst_list, 0.0)),
            }
            processed_invoice_data['items'].append(item_entry)

    print(processed_invoice_data)
    return processed_invoice_data


def update_products_from_invoice(invoice_data_processed, request):

    for item in invoice_data_processed['items']:

        if not Product.objects.filter(
            user=request.user,
            product_name=item['invoice_product'],
            product_hsn=item['invoice_hsn'],
            product_unit=item['invoice_unit'],
            product_gst_percentage=item['invoice_gst_percentage']
        ).exists():

            product = Product(
                user=request.user,
                product_name=item['invoice_product'],
                product_hsn=item['invoice_hsn'],
                product_unit=item['invoice_unit'],
                product_gst_percentage=item['invoice_gst_percentage'],
                product_rate_with_gst=item['invoice_rate_with_gst']
            )

            product.save()
            

            


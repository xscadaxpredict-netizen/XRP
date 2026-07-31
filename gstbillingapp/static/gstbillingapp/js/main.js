var invoice_item_row_counter = $('#invoice-form-items-table-body tr').length || 1;
var fuse_customers;
var xshot_prefix = window.location.pathname.startsWith('/xshot') ? '/xshot' : '';

// ADDING INVOICE ROWS ===================================================
function add_invoice_item_row() {
    invoice_item_row_counter++;

    var lastRow = $('#invoice-form-items-table-body >tr:last');
    
    // Destroy Select2 on the last row temporarily to clone cleanly
    var originalSelect = lastRow.find('select.product_search_input');
    if (originalSelect.hasClass("select2-hidden-accessible")) {
        originalSelect.select2('destroy');
    }
    
    var newRow = lastRow.clone(false);
    
    // Re-initialize select2 on the original row
    if (originalSelect.length > 0) {
        init_select2(originalSelect[0]);
    }
    
    // Clean up the cloned select
    var clonedSelect = newRow.find('select.product_search_input');
    clonedSelect.val(null); // Clear selection but keep options!
    clonedSelect.removeAttr('data-select2-id');

    newRow.find('input').val('');
    newRow.find('td:first').html(invoice_item_row_counter);
    newRow.removeAttr('data-select2-id');

    /* attach calculation to new row */
    newRow.find('input[name=invoice-qty], input[name=invoice-gst-percentage], input[name=invoice-rate-with-gst]')
        .change(function(){
            update_amounts($(this));
        });

    newRow.insertAfter(lastRow);
    
    if (clonedSelect.length > 0) {
        init_select2(clonedSelect[0]);
    }
}

function setup_invoice_rows() {

    $("#invoice-form-addrow").click(function(event) {
        event.preventDefault();
        add_invoice_item_row();
    });

    $(document).on('click', '.remove-invoice-row', function() {
        var tbody = $('#invoice-form-items-table-body');
        if (tbody.find('tr').length > 1) {
            $(this).closest('tr').remove();
            
            // Re-number the rows
            tbody.find('tr').each(function(index) {
                $(this).find('.invoice-item-slno').html(index + 1);
            });
            
            // Update total rows
            invoice_item_row_counter = tbody.find('tr').length;
            update_invoice_totals();
        } else {
            // If it's the last row, just clear the inputs
            var row = $(this).closest('tr');
            row.find('input').not(':button, :submit, :reset, :hidden, :checkbox, :radio').val('');
            
            var select = row.find('select.product_search_input');
            if (select.length) {
                select.val(null).trigger('change');
            }
            update_invoice_totals();
        }
    });

}

// UPDATING INVOICE TOTALS ================================================

function update_invoice_totals() {

    // amount without gst
    sum_amt_without_gst = 0
    $('input[name=invoice-amt-without-gst]').each(function(){
        sum_amt_without_gst += parseFloat($(this).val());
    });
    $('input[name=invoice-total-amt-without-gst]').val(sum_amt_without_gst.toFixed(2));

    // amount sgst
    sum_amt_sgst = 0
    $('input[name=invoice-amt-sgst]').each(function(){
        sum_amt_sgst += parseFloat($(this).val());
    });
    $('input[name=invoice-total-amt-sgst]').val(sum_amt_sgst.toFixed(2));

    // amount cgst
    sum_amt_cgst = 0
    $('input[name=invoice-amt-cgst]').each(function(){
        sum_amt_cgst += parseFloat($(this).val());
    });
    $('input[name=invoice-total-amt-cgst]').val(sum_amt_cgst.toFixed(2));

    // amount igst
    sum_amt_igst = 0
    $('input[name=invoice-amt-igst]').each(function(){
        sum_amt_igst += parseFloat($(this).val());
    });
    $('input[name=invoice-total-amt-igst]').val(sum_amt_igst.toFixed(2));

    sum_amt_with_gst = 0
    $('input[name=invoice-amt-with-gst]').each(function(){
        sum_amt_with_gst += parseFloat($(this).val());
    });
    $('input[name=invoice-total-amt-with-gst]').val(sum_amt_with_gst.toFixed(2));

}


// AUTO CALCULATE ITEM AMOUNTS =============================================

function initialize_auto_calculation(){
    update_amounts($('#invoice-form-items-table-body input[name=invoice-qty]:first'));
    $('input[name=invoice-qty], input[name=invoice-gst-percentage], input[name=invoice-rate-with-gst]').change(function (){
        update_amounts($(this));
    });
}

function update_amounts(element){
    var product = element.parent().parent().find('input[name=invoice-product]').val();
    var qty = parseInt(element.parent().parent().find('input[name=invoice-qty]').val()) || 0;
    var rate_with_gst = parseFloat(element.parent().parent().find('input[name=invoice-rate-with-gst]').val()) || 0;
    var gst_percentage = parseFloat(element.parent().parent().find('input[name=invoice-gst-percentage]').val()) || 0;

    var rate_without_gst = (rate_with_gst * 100.0) / (100.0 + gst_percentage);
    var amt_without_gst = rate_without_gst * qty;

    var sgst;
    var cgst;
    var igst;
    if(product == ""){
        sgst = 0;
        cgst = 0;
        igst = 0;
        amt_without_gst = 0;
    }
    else {
        if($('input[name=igstcheck]').is(':checked')){
            sgst = 0;
            cgst = 0;
            igst = amt_without_gst * gst_percentage / 100;
        }
        else {
            sgst = amt_without_gst * gst_percentage / 200;
            cgst = amt_without_gst * gst_percentage / 200;
            igst = 0;

        }
    }
    var amt_with_gst = amt_without_gst + cgst + sgst + igst;

    element.parent().parent().find('input[name=invoice-rate-without-gst]').val(rate_without_gst.toFixed(2));
    element.parent().parent().find('input[name=invoice-amt-without-gst]').val(amt_without_gst.toFixed(2));
    element.parent().parent().find('input[name=invoice-amt-sgst]').val(sgst.toFixed(2));
    element.parent().parent().find('input[name=invoice-amt-cgst]').val(cgst.toFixed(2));
    element.parent().parent().find('input[name=invoice-amt-igst]').val(igst.toFixed(2));
    element.parent().parent().find('input[name=invoice-amt-with-gst]').val(amt_with_gst.toFixed(2));

    update_invoice_totals();

}


// CUSTOMER SEARCH ========================================================

function customer_result_to_domstr(result) {
    var domstr = "<div class='customer-search-result' data-customer='" + JSON.stringify(result) + "'>"+
    "<div>"+ result['customer_name'] + "</div>" +
    "<div>"+ result['customer_address'] + "</div>" +
    "<div>"+ result['customer_phone'] + "</div>" +
    "<div>"+ result['customer_gst'] + "</div>" +
    "<div>"+ result['customer_pan'] + "</div>" +
    "</div>";
     return domstr;
}

function customer_result_click() {
    console.log("UPDATE THE FORM WITH SEARCH RESULT");

    // Parse the selected customer data
    customer_data_json = JSON.parse($(this).attr('data-customer'));

    // Populate form fields with customer details
    $('#customer-name-input').val(customer_data_json['customer_name']);
    $('#customer-address-input').val(customer_data_json['customer_address']);
    $('#customer-phone-input').val(customer_data_json['customer_phone']);
    $('#customer-gst-input').val(customer_data_json['customer_gst']);
    $('#customer-pan-input').val(customer_data_json['customer_pan']);

    // Fetch and update the PO Number (Vehicle Numbers) for existing customers
    fetch_vehicle_number(customer_data_json['customer_name']);
}

function fetch_vehicle_number(customerName) {
    if (!customerName) return;

    console.log("Fetching vehicle numbers for:", customerName);

    fetch(`${xshot_prefix}/get-all-vehicle-numbers-by-name/?customer_name=${encodeURIComponent(customerName)}`)
        .then(response => response.json())
        .then(data => {
            console.log("Vehicle numbers response:", data);

            var vehicleDropdown = $("select[name='vehicle-number-dropdown']");
            vehicleDropdown.empty(); // Clear previous options

            if (data.vehicle_numbers.length > 0) {
                // Populate dropdown with fetched vehicle numbers
                data.vehicle_numbers.forEach(function(vehicle_number) {
                    vehicleDropdown.append(new Option(vehicle_number, vehicle_number));
                });

                console.log("Vehicle numbers updated in dropdown:", data.vehicle_numbers);
            } else {
                // Allow manual entry if no vehicles are found
                vehicleDropdown.append(new Option("No PO found", ""));
            }
        })
        .catch(error => console.error("Error fetching vehicle number:", error));
}


function initialize_fuse_customers_search_bar() {
    console.log("INITIALIZING CUSTOMER SEARCH");

    $(".customer_search_area").focusin(function() {
        $("#customer_search_bar").show();
        var input = $('.customer_search_input');
        var val = input.val();
        update_customer_search_bar(val);
    });

    $(document).bind('focusin click',function(e) {
        if ($(e.target).closest('#customer_search_bar, .customer_search_area').length) return;
        $('#customer_search_bar').hide();
    });

    $(".customer_search_input").on("input", function(e) {
        $("#customer_search_bar").show();
        var input = $(this);
        var val = input.val();
        update_customer_search_bar(val);
    });
}

function update_customer_search_bar(search_string){
    console.log("Update customer search bar with query: " + search_string);
    results = fuse_customers.search(search_string);
    // console.log(results);
    $("#customer_search_bar").empty();
    for (var i = 0; i < results.length; i++) {
        $("#customer_search_bar").append(customer_result_to_domstr(results[i]));
    }
    $('.customer-search-result').click(customer_result_click);
}


function initialize_fuse_customers () {
    // fetch customer data
    $.getJSON( xshot_prefix + "/customersjson", function( data ) {
        var fuse_customer_options = {
            shouldSort: true,
            threshold: 0.6,
            location: 0,
            distance: 100,
            maxPatternLength: 32,
            minMatchCharLength: 1,
            keys: [
            "customer_name",
            "customer_address",
            "customer_gst",
            "customer_pan",
            ]
        };
        fuse_customers = new Fuse(data, fuse_customer_options);

        // initialize the search bar
        initialize_fuse_customers_search_bar();
    });
}


// PRODUCT SEARCH ========================================================

var products_data = [];

function init_select2(element) {
    if ($(element).hasClass("select2-hidden-accessible")) return;
    
    $(element).select2({
        theme: 'bootstrap4',
        tags: true, // allows creating new items
        placeholder: "Select or Add Product",
        width: '100%'
    });

    $(element).on('select2:select', function (e) {
        // e.params.data.id contains the value of the selected option
        var value = e.params.data.id;
        var product = products_data.find(p => p.product_name === value);
        var row = $(this).closest('tr');
        
        if (product) {
            row.find('input[name=invoice-hsn]').val(product.product_hsn);
            row.find('input[name=invoice-unit]').val(product.product_unit);
            row.find('input[name=invoice-rate-with-gst]').val(product.product_rate_with_gst);
            row.find('input[name=invoice-gst-percentage]').val(product.product_gst_percentage);
            
            // Trigger auto calculation if quantity already exists
            var qtyInput = row.find('input[name=invoice-qty]');
            if(qtyInput.val()) {
                update_amounts(qtyInput);
            }
        } else {
            // For newly created products, clear fields to let user fill them manually
            row.find('input[name=invoice-hsn]').val('');
            row.find('input[name=invoice-unit]').val('');
            row.find('input[name=invoice-rate-with-gst]').val('');
            row.find('input[name=invoice-gst-percentage]').val('');
        }
    });
}

function initialize_products () {
    $.getJSON( xshot_prefix + "/productsjson", function( data ) {
        products_data = data;
        
        $('.product_search_input').each(function() {
            var select = $(this);
            // Append options directly to the DOM
            data.forEach(function(p) {
                if (!select.find("option").filter(function() { return $(this).val() === p.product_name; }).length) {
                    select.append(new Option(p.product_name, p.product_name, false, false));
                }
            });
            init_select2(this);
        });
    });
}

function initialize_instant_validation() {
    $('#invoice-form').on('blur input change', 'input, select, textarea', function() {
        var $el = $(this);
        if ($el.hasClass('select2-search__field') || $el.attr('type') === 'submit' || $el.attr('type') === 'button') return;
        if ($el.attr('type') === 'checkbox' && !$el.prop('required')) return;

        if (!this.checkValidity()) {
            $el.addClass('is-invalid').removeClass('is-valid');
            var feedback;
            if ($el.hasClass('select2-hidden-accessible')) {
                var s2container = $el.next('.select2-container');
                s2container.find('.select2-selection').addClass('border-danger').removeClass('border-success');
                feedback = s2container.next('.invalid-feedback');
                if (feedback.length === 0) {
                    feedback = $('<div class="invalid-feedback d-block mt-1"></div>');
                    s2container.after(feedback);
                }
            } else {
                feedback = $el.siblings('.invalid-feedback');
                if (feedback.length === 0) {
                    feedback = $('<div class="invalid-feedback"></div>');
                    $el.after(feedback);
                }
            }
            feedback.text(this.validationMessage);
        } else {
            $el.removeClass('is-invalid');
            if ($el.val()) {
                $el.addClass('is-valid');
                if ($el.hasClass('select2-hidden-accessible')) {
                    $el.next('.select2-container').find('.select2-selection').addClass('border-success').removeClass('border-danger');
                }
            } else {
                $el.removeClass('is-valid');
                if ($el.hasClass('select2-hidden-accessible')) {
                    $el.next('.select2-container').find('.select2-selection').removeClass('border-success border-danger');
                }
            }
            
            if ($el.hasClass('select2-hidden-accessible')) {
                $el.next('.select2-container').next('.invalid-feedback').remove();
            } else {
                $el.siblings('.invalid-feedback').remove();
            }
        }
    });
}


// START =============================================================

$(document).ready(function() {

    // Initialize invoice row addition
    setup_invoice_rows();

    // Initialize customer search
    initialize_fuse_customers();

    // Initialize product search
    initialize_products();

    // Initialize auto calculation of amounts
    initialize_auto_calculation();
    
    // Initialize instant inline validation
    initialize_instant_validation();

    // Initialize igst toggle
    $("input[name=igstcheck]").change(function() {
            $('input[name=invoice-qty]').each(function(){
                update_amounts($( this ));
            });
    });

    // Auto-fill Customer PAN from Customer GST
    $('#customer-gst-input').on('input', function() {
        var gstValue = $(this).val();
        if (gstValue.length >= 2) {
            // A PAN is characters 3 to 12 of a standard GSTIN (indices 2 to 11)
            var panValue = gstValue.substring(2, 12);
            $('#customer-pan-input').val(panValue).trigger('input');
        } else {
            $('#customer-pan-input').val('').trigger('input');
        }
    });

    // Auto-fill Shipping PAN from Shipping GST
    $('#shipping-gst-input').on('input', function() {
        var gstValue = $(this).val();
        if (gstValue.length >= 2) {
            var panValue = gstValue.substring(2, 12);
            $('#shipping-tin-input').val(panValue).trigger('input');
        } else {
            $('#shipping-tin-input').val('').trigger('input');
        }
    });

    // Show the invoice form
    $("#invoice-form")[0].hidden = false;

});

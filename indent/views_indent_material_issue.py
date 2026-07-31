@login_required
def project_material_issue_from_indent(request, project_id, indent_id=None):
    """Issue materials from an indent to a project"""
    project = get_object_or_404(Project, pk=project_id)
    
    # If no indent_id, show indent selection page
    if not indent_id:
        indents = Indent.objects.filter(project=project).order_by('-created_at')
        return render(request, "indent/select_indent_for_issue.html", {
            "project": project,
            "indents": indents,
        })
    
    # Get the selected indent
    indent = get_object_or_404(Indent, pk=indent_id, project=project)
    
    if request.method == "POST":
        # Process multiple items
        items_data = []
        errors = []
        
        # Parse form data for each item
        for key in request.POST:
            if key.startswith('selected_'):
                item_id = key.replace('selected_', '')
                if request.POST.get(key) == 'on':
                    try:
                        indent_item = IndentItem.objects.get(pk=item_id)
                        qty = int(request.POST.get(f'qty_{item_id}', 0))
                        price = float(request.POST.get(f'price_{item_id}', 0))
                        
                        if qty <= 0:
                            errors.append(f"Invalid quantity for {indent_item.product_name}")
                            continue
                        
                        # Find matching stock item
                        stock = StockItem.objects.filter(product_name=indent_item.product_name).first()
                        if not stock:
                            errors.append(f"No stock found for {indent_item.product_name}")
                            continue
                        
                        if stock.quantity < qty:
                            errors.append(f"Insufficient stock for {indent_item.product_name}. Available: {stock.quantity}, Requested: {qty}")
                            continue
                        
                        items_data.append({
                            'indent_item': indent_item,
                            'stock': stock,
                            'qty': qty,
                            'price': price,
                        })
                    except (IndentItem.DoesNotExist, ValueError) as e:
                        errors.append(f"Error processing item: {str(e)}")
        
        if errors:
            for error in errors:
                messages.error(request, f"❌ {error}")
        
        if items_data and not errors:
            # Issue all items
            total_value = 0
            issued_count = 0
            
            for item_data in items_data:
                stock = item_data['stock']
                qty = item_data['qty']
                price = item_data['price']
                
                # Reduce stock
                stock.quantity -= qty
                stock.save()
                
                # Create stock log
                StockLog.objects.create(
                    stock_item=stock,
                    change_quantity=-qty,
                    transaction_type='ISSUE',
                    description=f"Issued to Project #{project.id} - {project.name} (from Indent #{indent.indent_number})",
                    user=request.user
                )
                
                # Create material issue
                MaterialIssue.objects.create(
                    project=project,
                    stock_item=stock,
                    issued_qty=qty,
                    unit_price=price,
                    issued_by=request.user
                )
                
                total_value += qty * price
                issued_count += 1
            
            messages.success(
                request,
                f"✅ Successfully issued {issued_count} items from Indent #{indent.indent_number} to {project.name}. Total value: ₹{total_value:.2f}"
            )
            return redirect("project_detail", pk=project.id)
        elif not items_data:
            messages.warning(request, "⚠️ No items selected for issuance")
    
    # GET request - show indent items
    indent_items_data = []
    for item in indent.items.all():
        # Find matching stock
        stock = StockItem.objects.filter(product_name=item.product_name).first()
        
        # Get last purchase price
        last_price = 0
        if stock:
            last_grn_item = GRNItem.objects.filter(
                purchase_item__product_name=item.product_name
            ).order_by('-grn__received_date').first()
            
            if last_grn_item and last_grn_item.purchase_item:
                last_price = float(last_grn_item.purchase_item.unit_price)
        
        indent_items_data.append({
            'indent_item': item,
            'stock': stock,
            'available_qty': stock.quantity if stock else 0,
            'requested_qty': item.quantity,
            'last_price': last_price,
            'has_stock': stock is not None,
            'sufficient_stock': stock and stock.quantity >= item.quantity if stock else False,
        })
    
    return render(request, "indent/project_material_issue_from_indent.html", {
        "project": project,
        "indent": indent,
        "indent_items_data": indent_items_data,
    })

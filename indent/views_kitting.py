import openpyxl
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import (
    MachineKit, KitComponent, StockItem, Vendor, VendorStock, 
    Department, ProductionOrder, Indent, IndentItem, Project,
    InternalIndent, InternalIndentItem
)
import uuid
import random

@login_required
def upload_kit_excel(request):
    po_id = request.GET.get('po_id')
    if request.method == 'POST':
        excel_file = request.FILES.get('kit_file')
        kit_name = request.POST.get('kit_name')
        
        if not excel_file or not kit_name:
            messages.error(request, "Please provide both Kit Name and Excel File.")
            if po_id:
                return redirect(f"/indent/kitting/upload/?po_id={po_id}")
            return redirect('upload_kit_excel')

        try:
            kit, created = MachineKit.objects.get_or_create(name=kit_name)
            if not created:
                kit.components.all().delete()
            
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            sheet = wb.active
            
            current_category = "General"
            current_sfg_component = None
            
            dept_col_idx = None
            type_col_idx = None
            
            for row in sheet.iter_rows(min_row=1, values_only=True):
                non_empty_cells = [c for c in row if c is not None and str(c).strip() != '']
                
                # Check if it's a category header (e.g., just "IoT" or "ELECTRICALS" in the whole row)
                if len(non_empty_cells) == 1 and str(non_empty_cells[0]).strip().upper() not in ['TOTAL', 'SL NO']:
                    current_category = str(non_empty_cells[0]).strip()
                    current_sfg_component = None
                    continue
                
                # Check if it's a column header row
                if len(non_empty_cells) > 1 and row[1] and str(row[1]).strip().upper() == 'ITEM':
                    # Find where 'DEPARTMENT' and 'TYPE' are for this section
                    for col_idx, cell in enumerate(row):
                        if cell and str(cell).strip().upper() == 'DEPARTMENT':
                            dept_col_idx = col_idx
                        elif cell and str(cell).strip().upper() in ['TYPE', 'ITEM TYPE']:
                            type_col_idx = col_idx
                    continue
                
                # Check if this is a total row
                if row[4] == 'TOTAL' or str(row[1]).strip() == 'TOTAL' or str(row[0]).strip() == 'TOTAL':
                    continue

                if not row[1] or str(row[1]).strip() == '':
                    continue # Skip empty item rows
                    
                item_name = str(row[1]).strip()
                
                uom = str(row[2]).strip() if row[2] else ""
                
                try:
                    qty = Decimal(str(row[3])) if row[3] else Decimal('1.0')
                except:
                    qty = Decimal('1.0')
                    
                try:
                    price = Decimal(str(row[4])) if row[4] else Decimal('0.0')
                except:
                    price = Decimal('0.0')
                    
                remarks = str(row[6]).strip() if row[6] and str(row[6]).lower() != 'none' else ""
                vendor_name = str(row[7]).strip() if row[7] and str(row[7]).lower() != 'none' else "LOCAL VENDOR"
                
                # Map category to Department
                if dept_col_idx is not None and len(row) > dept_col_idx and row[dept_col_idx]:
                    dept_name = str(row[dept_col_idx]).strip()
                else:
                    cat_upper = str(current_category).upper()
                    dept_name = "MSF" # Default fallback
                    
                    if "IOT" in cat_upper:
                        dept_name = "ESD"
                    elif any(x in cat_upper for x in ["ELECTRO MECHANICALS", "POWER SYSTEM", "ELECTRICAL"]):
                        dept_name = "WAH"
                    elif any(x in cat_upper for x in ["TANKS", "FILTERATION", "MISC", "ACCESSORIES"]):
                        dept_name = "ALF"
                    elif "PLASTIC" in cat_upper:
                        dept_name = "PSF"
                    elif "STRUCTURE" in cat_upper:
                        dept_name = "MSF"
                    
                department, _ = Department.objects.get_or_create(name=dept_name)
                
                # Check for SFG
                is_sfg = False
                if type_col_idx is not None and len(row) > type_col_idx and row[type_col_idx]:
                    if str(row[type_col_idx]).strip().upper() == 'SFG':
                        is_sfg = True
                
                # Get or create Vendor
                vendor, _ = Vendor.objects.get_or_create(name=vendor_name)
                
                # Get or create StockItem
                stock_item, created_item = StockItem.objects.get_or_create(
                    product_name=item_name,
                    defaults={
                        'stock_type': 'semifinished' if is_sfg else 'raw',
                        'department': department.name,
                        'quantity': 0,
                    }
                )
                
                # Update stock_type if it was created as raw but is now SFG
                if not created_item and is_sfg and stock_item.stock_type != 'semifinished':
                    stock_item.stock_type = 'semifinished'
                    stock_item.save()
                
                # Link Vendor to StockItem
                VendorStock.objects.get_or_create(
                    stock_item=stock_item,
                    vendor=vendor,
                    defaults={'price': price, 'lead_time': 5}
                )
                
                # Add to Kit
                component = KitComponent.objects.create(
                    kit=kit,
                    stock_item=stock_item,
                    category_name=current_category,
                    department=department,
                    required_quantity=qty,
                    uom=uom,
                    remarks=remarks,
                    parent_component=None if is_sfg else current_sfg_component
                )
                
                if is_sfg:
                    current_sfg_component = component
                
            messages.success(request, f"Kit '{kit_name}' imported successfully.")
            
            if po_id:
                po = get_object_or_404(ProductionOrder, id=po_id)
                po.machine_kit = kit
                po.save()
                messages.success(request, f"Kit '{kit.name}' automatically attached to PO '{po.order_number}'.")
                return redirect('po_kitting_dashboard', po_id=po.id)
                
            return redirect('machine_kits_list')
            
        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")
            if po_id:
                return redirect(f"/indent/kitting/upload/?po_id={po_id}")
            return redirect('upload_kit_excel')
            
    return render(request, 'indent/kitting/upload_excel.html', {'po_id': po_id})

@login_required
def machine_kits_list(request):
    kits = MachineKit.objects.all()
    return render(request, 'indent/kitting/kits_list.html', {'kits': kits})

@login_required
def machine_kit_detail(request, kit_id):
    kit = get_object_or_404(MachineKit, id=kit_id)
    components = kit.components.all().select_related('stock_item', 'department')
    
    grouped_shortages = {}
    for comp in components:
        req_qty = comp.required_quantity
        in_stock = comp.stock_item.quantity
        shortage = req_qty - in_stock if req_qty > in_stock else 0
        
        vendor_stock = VendorStock.objects.filter(stock_item=comp.stock_item).first()
        cost = float(shortage) * float(vendor_stock.price if vendor_stock and vendor_stock.price else 0.0)
        
        dept_name = comp.department.name if comp.department else "Unassigned"
        if dept_name not in grouped_shortages:
            grouped_shortages[dept_name] = {
                'items': [],
                'stats': {
                    'total': 0,
                    'in_stock': 0,
                    'need_purchase': 0,
                    'cost': 0.0
                }
            }
            
        grouped_shortages[dept_name]['items'].append({
            'component': comp,
            'req_qty': req_qty,
            'in_stock': in_stock,
            'shortage': shortage,
            'vendor_stock': vendor_stock
        })
        
        grouped_shortages[dept_name]['stats']['total'] += 1
        if shortage > 0:
            grouped_shortages[dept_name]['stats']['need_purchase'] += 1
            grouped_shortages[dept_name]['stats']['cost'] += cost
        else:
            grouped_shortages[dept_name]['stats']['in_stock'] += 1
            
    # Calculate complete BOM stats
    total_stats = {'total': 0, 'in_stock': 0, 'need_purchase': 0, 'cost': 0.0}
    for data in grouped_shortages.values():
        total_stats['total'] += data['stats']['total']
        total_stats['in_stock'] += data['stats']['in_stock']
        total_stats['need_purchase'] += data['stats']['need_purchase']
        total_stats['cost'] += data['stats']['cost']
        
    return render(request, 'indent/kitting/kit_detail.html', {
        'kit': kit,
        'grouped_shortages': grouped_shortages,
        'total_stats': total_stats
    })

@login_required
def po_kitting_dashboard(request, po_id):
    po = get_object_or_404(ProductionOrder, id=po_id)
    if not po.machine_kit:
        messages.error(request, "This Production Order does not have a Machine Kit attached.")
        return redirect('production_order_detail', pk=po.id)
        
    components = po.machine_kit.components.all().select_related('stock_item', 'department')
    
    # Optional logic: Multiply by PO quantity if PO has a quantity field (currently PO doesn't have it explicitly, assuming 1 machine per PO)
    multiplier = 1
    
    grouped_shortages = {}
    for comp in components:
        req_qty = comp.required_quantity * multiplier
        in_stock = comp.stock_item.quantity
        shortage = req_qty - in_stock if req_qty > in_stock else 0
        
        vendor_stock = VendorStock.objects.filter(stock_item=comp.stock_item).first()
        cost = float(shortage) * float(vendor_stock.price if vendor_stock and vendor_stock.price else 0.0)
        
        dept_name = comp.department.name if comp.department else "Unassigned"
        if dept_name not in grouped_shortages:
            grouped_shortages[dept_name] = {
                'items': [],
                'stats': {
                    'total': 0,
                    'in_stock': 0,
                    'need_purchase': 0,
                    'cost': 0.0
                }
            }
            
        grouped_shortages[dept_name]['items'].append({
            'component': comp,
            'req_qty': req_qty,
            'in_stock': in_stock,
            'shortage': shortage,
            'vendor_stock': vendor_stock
        })
        
        grouped_shortages[dept_name]['stats']['total'] += 1
        if shortage > 0:
            grouped_shortages[dept_name]['stats']['need_purchase'] += 1
            grouped_shortages[dept_name]['stats']['cost'] += cost
        else:
            grouped_shortages[dept_name]['stats']['in_stock'] += 1
            
    # Calculate complete BOM stats
    total_stats = {'total': 0, 'in_stock': 0, 'need_purchase': 0, 'cost': 0.0}
    for data in grouped_shortages.values():
        total_stats['total'] += data['stats']['total']
        total_stats['in_stock'] += data['stats']['in_stock']
        total_stats['need_purchase'] += data['stats']['need_purchase']
        total_stats['cost'] += data['stats']['cost']
        
    if request.method == 'POST' and 'generate_indent' in request.POST:
        # Group shortages by Department to create Indents
        dept_shortages = {}
        for dept, data in grouped_shortages.items():
            for s in data['items']:
                if s['shortage'] > 0:
                    dept_obj = s['component'].department
                    if dept_obj not in dept_shortages:
                        dept_shortages[dept_obj] = []
                    dept_shortages[dept_obj].append(s)
                
        indents_created = 0
        for dept, items in dept_shortages.items():
            indent_number = f"IND-KIT-{uuid.uuid4().hex[:6].upper()}"
            indent = Indent.objects.create(
                title=f"Kitting Shortage for PO-{po.order_number}",
                indent_number=indent_number,
                department=dept,
                created_by=request.user,
                production_order=po,
                status='draft'
            )
            indents_created += 1
            
            for item in items:
                comp = item['component']
                vs = item['vendor_stock']
                
                IndentItem.objects.create(
                    indent=indent,
                    product_name=comp.stock_item.product_name,
                    product_code=comp.stock_item.product_code,
                    quantity=item['shortage'],
                    unit=comp.uom,
                    remarks=comp.remarks,
                    shortage_qty=item['shortage'],
                    source_type='purchase',
                    vendor=vs.vendor if vs else None,
                    unit_price=vs.price if vs else 0.0
                )
                
        messages.success(request, f"Generated {indents_created} indents for shortages.")
        return redirect('indent_list')
        
    return render(request, 'indent/kitting/po_dashboard.html', {
        'po': po,
        'grouped_shortages': grouped_shortages,
        'kit': po.machine_kit,
        'total_stats': total_stats
    })

@login_required
def project_kitting_dashboard(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.machine_kit:
        messages.error(request, "This Project does not have a Machine Kit attached.")
        return redirect('project_list')
        
    components = project.machine_kit.components.all().select_related('stock_item', 'department')
    
    # Optional logic: Multiply by PO quantity if PO has a quantity field (currently PO doesn't have it explicitly, assuming 1 machine per PO)
    multiplier = 1
    
    grouped_shortages = {}
    for comp in components:
        req_qty = comp.required_quantity * multiplier
        in_stock = comp.stock_item.quantity
        shortage = req_qty - in_stock if req_qty > in_stock else 0
        
        vendor_stock = VendorStock.objects.filter(stock_item=comp.stock_item).first()
        cost = float(shortage) * float(vendor_stock.price if vendor_stock and vendor_stock.price else 0.0)
        
        dept_name = comp.department.name if comp.department else "Unassigned"
        if dept_name not in grouped_shortages:
            grouped_shortages[dept_name] = {
                'items': [],
                'stats': {
                    'total': 0,
                    'in_stock': 0,
                    'need_purchase': 0,
                    'cost': 0.0
                }
            }
            
        grouped_shortages[dept_name]['items'].append({
            'component': comp,
            'req_qty': req_qty,
            'in_stock': in_stock,
            'shortage': shortage,
            'vendor_stock': vendor_stock,
            'is_sfg': comp.stock_item.stock_type == 'semifinished'
        })
        
        grouped_shortages[dept_name]['stats']['total'] += 1
        if shortage > 0:
            grouped_shortages[dept_name]['stats']['need_purchase'] += 1
            grouped_shortages[dept_name]['stats']['cost'] += cost
        else:
            grouped_shortages[dept_name]['stats']['in_stock'] += 1
            
    # Calculate complete BOM stats
    total_stats = {'total': 0, 'in_stock': 0, 'need_purchase': 0, 'cost': 0.0}
    for data in grouped_shortages.values():
        total_stats['total'] += data['stats']['total']
        total_stats['in_stock'] += data['stats']['in_stock']
        total_stats['need_purchase'] += data['stats']['need_purchase']
        total_stats['cost'] += data['stats']['cost']
        
    if request.method == 'POST' and 'generate_indent' in request.POST:
        indents_created = 0
        internal_indents_created = 0
        
        # Group components by department, and separate by sfg vs raw
        dept_raw_shortages = {}
        dept_sfg_shortages = {}
        
        for dept, data in grouped_shortages.items():
            for s in data['items']:
                # Check if we should order this item
                force_generate = request.POST.get(f"force_sfg_{s['component'].id}")
                qty_to_order = 0
                if force_generate:
                    qty_to_order = s['req_qty']
                elif s['shortage'] > 0:
                    qty_to_order = s['shortage']
                    
                if qty_to_order > 0:
                    dept_obj = s['component'].department
                    
                    if s['is_sfg']:
                        if dept_obj not in dept_sfg_shortages:
                            dept_sfg_shortages[dept_obj] = []
                        s['qty_to_order'] = qty_to_order
                        dept_sfg_shortages[dept_obj].append(s)
                    else:
                        if dept_obj not in dept_raw_shortages:
                            dept_raw_shortages[dept_obj] = []
                        s['qty_to_order'] = qty_to_order
                        dept_raw_shortages[dept_obj].append(s)

        # Create Material Indents (raw)
        for dept, items in dept_raw_shortages.items():
            indent_number = f"IND-KIT-{uuid.uuid4().hex[:6].upper()}"
            indent = Indent.objects.create(
                title=f"Kitting Shortage for Project {project.name}",
                indent_number=indent_number,
                department=dept,
                created_by=request.user,
                project=project,
                status='draft'
            )
            indents_created += 1
            
            for item in items:
                comp = item['component']
                vs = item['vendor_stock']
                
                IndentItem.objects.create(
                    indent=indent,
                    product_name=comp.stock_item.product_name,
                    product_code=comp.stock_item.product_code,
                    quantity=item['qty_to_order'],
                    unit=comp.uom,
                    remarks=comp.remarks,
                    shortage_qty=item['qty_to_order'],
                    source_type='purchase',
                    vendor=vs.vendor if vs else None,
                    unit_price=vs.price if vs else 0.0
                )

        # Create Production Items (SFG)
        for dept, items in dept_sfg_shortages.items():
            if dept is None:
                continue
                
            internal_indent, created = InternalIndent.objects.get_or_create(
                project=project,
                department=dept,
                defaults={
                    'indent_number': f"XPINT-{uuid.uuid4().hex[:6].upper()}",
                    'created_by': request.user,
                    'status': 'internal'
                }
            )
            if created:
                internal_indents_created += 1
                
            for item in items:
                comp = item['component']
                InternalIndentItem.objects.create(
                    internal_indent=internal_indent,
                    item_name=comp.stock_item.product_name,
                    quantity=item['qty_to_order'],
                    requested_by_dept=dept
                )
                
        messages.success(request, f"Generated {indents_created} material indents and updated {len(dept_sfg_shortages)} production departments.")
        return redirect('indent_list')
        
    return render(request, 'indent/kitting/project_dashboard.html', {
        'project': project,
        'grouped_shortages': grouped_shortages,
        'kit': project.machine_kit,
        'total_stats': total_stats
    })

@login_required
def attach_kit_to_po(request, po_id):
    po = get_object_or_404(ProductionOrder, id=po_id)
    if request.method == 'POST':
        kit_id = request.POST.get('kit_id')
        if kit_id:
            kit = get_object_or_404(MachineKit, id=kit_id)
            po.machine_kit = kit
            po.save()
            messages.success(request, f"Successfully attached Kit '{kit.name}' to Production Order '{po.order_number}'.")
        else:
            po.machine_kit = None
            po.save()
            messages.info(request, f"Detached Kit from Production Order '{po.order_number}'.")
            
    return redirect('production_order_detail', pk=po.id)

@login_required
def download_kit_template(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from django.http import HttpResponse

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kit BOM"

    # Category 1
    ws.append(["IoT"])
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

    # Headers
    headers = ["SL NO", "ITEM", "UOM", "QTY", "PRICE", "TOTAL", "REMARKS", "VENDOR", "TYPE", "DEPARTMENT"]
    ws.append(headers)
    for cell in ws[2]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="ADD8E6", end_color="ADD8E6", fill_type="solid")

    # Data
    ws.append([1, "Smart Control Panel Assembly", "Nos", 1, 0, 0, "Top level assembly", "", "SFG", "ESD"])
    ws.append([2, "Raspberry Pi 4", "Nos", 2, 4500, 9000, "With casing", "TECH VENDOR", "RAW", "ESD"])
    ws.append([3, "Sensor Module", "Nos", 5, 200, 1000, "", "LOCAL VENDOR", "RAW", "ESD"])
    
    # Category 2
    ws.append([])
    ws.append(["ELECTRO MECHANICALS"])
    ws["A6"].font = Font(bold=True, size=14)
    ws["A6"].fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

    # Headers
    ws.append(headers)
    for cell in ws[7]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="ADD8E6", end_color="ADD8E6", fill_type="solid")

    ws.append([4, "Steel Frame Unit", "Nos", 1, 0, 0, "Welded frame", "", "SFG", "MSF"])
    ws.append([5, "Stepper Motor", "Nos", 4, 1500, 6000, "NEMA 17", "ROBO VENDOR", "RAW", "MSF"])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=kit_upload_template.xlsx'
    wb.save(response)
    return response

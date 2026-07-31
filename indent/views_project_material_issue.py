@login_required
def project_material_issue(request, project_id):
    """Issue material from stock to a project"""
    project = get_object_or_404(Project, pk=project_id)

    if request.method == "POST":
        form = MaterialIssueForm(request.POST)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.project = project
            issue.issued_by = request.user

            # get stock item and issued quantity from form
            stock_item = form.cleaned_data["stock_item"]
            issued_qty = form.cleaned_data["issued_qty"]

            # check stock availability
            stock = get_object_or_404(StockItem, pk=stock_item.id)
            if stock.quantity < issued_qty:
                messages.error(
                    request,
                    f"Not enough stock for {stock_item}. Available: {stock.quantity}"
                )
                return redirect("project_material_issue", project_id=project.id)

            # reduce stock
            stock.quantity -= issued_qty
            stock.save()

            StockLog.objects.create(
                stock_item=stock,
                change_quantity=-issued_qty,
                transaction_type='ISSUE',
                description=f"Issued to Project #{project.id} - {project.name}",
                user=request.user
            )

            # save issue
            issue.issued_qty = issued_qty
            issue.save()

            messages.success(
                request,
                f"Issued {issued_qty} units of {stock_item} to {project.name}."
            )
            return redirect("project_detail", pk=project.id)
    else:
        form = MaterialIssueForm(initial={"project": project})

    return render(request, "indent/project_material_issue.html", {
        "form": form,
        "project": project,
        "stock_items": StockItem.objects.all(),
    })

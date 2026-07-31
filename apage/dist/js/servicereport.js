let runCycleCount = 1; // Initial count of run cycles (global scope)

// Add a new run cycle row
var el_addRunCycleBtn = document.getElementById('addRunCycleBtn');
if (el_addRunCycleBtn) el_addRunCycleBtn.addEventListener('click', function() {
  runCycleCount++; // Increment the run cycle count

  // Create a new row
  const newRow = document.createElement('tr');
  newRow.id = `run_cycle_${runCycleCount}`;
  newRow.innerHTML = `
        <td>Run cycle ${runCycleCount}</td>
        <td><input type="time" class="form-control" name="run_time_${runCycleCount}"></td>
        <td><input type="time" class="form-control" name="end_time_${runCycleCount}"></td>
        <td><input type="checkbox" class="form-check-input" name="checked_run_${runCycleCount}"></td>
        <td><input type="checkbox" class="form-check-input" name="pass_run_${runCycleCount}"></td>
        <td><input type="checkbox" class="form-check-input" name="fail_run_${runCycleCount}"></td>
        <td><textarea class="form-control" name="remark_run_${runCycleCount}" rows="2" placeholder="Remark"></textarea></td>
    `;

  // Append the new row to the table body
  document.getElementById('runCycleRows').appendChild(newRow);

  // Update the hidden input with the current count
  document.getElementById('runCycleCount').value = runCycleCount;
});

// Ensure the DOM is fully loaded before setting up the remove button
document.addEventListener("DOMContentLoaded", function () {
  const runCycleRows = document.getElementById('runCycleRows');
  const removeAllBtn = document.getElementById('removeAllBtn');

  // Remove only the last row
  removeAllBtn.addEventListener('click', function () {
    if (runCycleRows.lastChild) {
      runCycleRows.removeChild(runCycleRows.lastChild); // Remove the last row
      runCycleCount--; // Decrease the count of run cycles
      document.getElementById('runCycleCount').value = runCycleCount; // Update the hidden field
    }
  });
});

  let remarkCount = 3;

  document.getElementById('add-remark-btn').addEventListener('click', () => {
    remarkCount++;
    const table = document.getElementById('remarks-table').getElementsByTagName('tbody')[0];
    const row = table.insertRow();
    const cell1 = row.insertCell(0);
    const cell2 = row.insertCell(1);

    cell1.textContent = remarkCount;
    cell2.innerHTML = `
      <div class="mb-3">
        <textarea class="form-control" name="remark_orm_${remarkCount}" rows="2" placeholder="Remark"></textarea>
      </div>
    `;
  });





   let spareCount = 3;

  document.getElementById('add-spare-btn').addEventListener('click', () => {
    spareCount++;
    const table = document.getElementById('spares-table').getElementsByTagName('tbody')[0];
    const row = table.insertRow();
    const cell1 = row.insertCell(0);
    const cell2 = row.insertCell(1);

    cell1.textContent = spareCount;
    cell2.innerHTML = `
      <div class="mb-3">
        <textarea class="form-control" name="spare_${spareCount}" rows="2" placeholder="Enter spare details"></textarea>
      </div>
    `;
  });





  document.getElementById('add-spare-btn').addEventListener('click', () => {
    spareCount++;
    const table = document.getElementById('spares-table').getElementsByTagName('tbody')[0];
    const row = table.insertRow();
    const cell1 = row.insertCell(0);
    const cell2 = row.insertCell(1);

    cell1.textContent = spareCount;
    cell2.innerHTML = `
      <div class="mb-3">
        <textarea class="form-control" name="spare_${spareCount}" rows="2" placeholder="Enter spare details"></textarea>
      </div>
    `;
  });





    document.addEventListener("DOMContentLoaded", function () {
    console.log("JavaScript Loaded");

    // Get the input element and error message container by ID
    const visitDateInput = document.getElementById("visit-date");
    const errorDiv = document.getElementById("visit-date-error");

    // Add event listener for the 'input' event on the visit-date field
    visitDateInput.addEventListener("input", function () {
        if (!visitDateInput.value) return;
        const selectedDate = new Date(visitDateInput.value + "T00:00:00"); // Convert selected date to Date object
        const today = new Date(); // Get today's date
        today.setHours(0, 0, 0, 0);  // Set today's time to 00:00:00 for comparison

        // Check if the selected date is in the future
        if (selectedDate > today) {
            errorDiv.style.display = "block"; // Show error message
            visitDateInput.classList.add("is-invalid"); // Add 'is-invalid' class to the input field for styling
        } else {
            errorDiv.style.display = "none"; // Hide error message
            visitDateInput.classList.remove("is-invalid"); // Remove the 'is-invalid' class
        }
    });
});
  
  document.addEventListener("DOMContentLoaded", function () {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('date').value = today;
  });

  document.addEventListener("DOMContentLoaded", function () {
    const attachmentSection = document.getElementById("attachment-section");
    const addAttachmentBtn = document.getElementById("add-attachment-btn");
  
    addAttachmentBtn.addEventListener("click", function () {
      // Create a new row for the attachment input and remove button
      const newRow = document.createElement("div");
      newRow.classList.add("row", "mt-2");
  
      // Create the column for the file input
      const inputCol = document.createElement("div");
      inputCol.classList.add("col-md-6", "mb-3");
  
      // Create the file input element
      const newInput = document.createElement("input");
      newInput.type = "file";
      newInput.name = "attachment[]";
      newInput.classList.add("form-control");
  
      // Append the input to the input column
      inputCol.appendChild(newInput);
  
      // Create the column for the remove button
      const buttonCol = document.createElement("div");
      buttonCol.classList.add("col-md-6", "mb-3", "d-flex", "align-items-center");
  
      // Create the remove button
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.classList.add("btn", "btn-outline-danger", "ms-2");
      removeBtn.textContent = "Remove";
  
      // Add event listener to remove the row
      removeBtn.addEventListener("click", function () {
        attachmentSection.removeChild(newRow);
      });
  
      // Append the remove button to the button column
      buttonCol.appendChild(removeBtn);
  
      // Append the columns to the new row
      newRow.appendChild(inputCol);
      newRow.appendChild(buttonCol);
  
      // Append the new row to the attachment section
      attachmentSection.appendChild(newRow);
    });
  });
  





    // JavaScript to add more textboxes dynamically
    document.getElementById('add-note-btn').addEventListener('click', function() {
        // Get the container for the notes
        var container = document.getElementById('notes-container');
        
        // Create a new input field
        var newInput = document.createElement('input');
        newInput.type = 'text';
        newInput.name = 'observation[]';
        newInput.placeholder = 'Observation ' + (container.children.length + 1); // Increment the placeholder
        newInput.classList.add('form-control', 'mb-2');
        
        // Append the new input field to the container
        container.appendChild(newInput);
      });
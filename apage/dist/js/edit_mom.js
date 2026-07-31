document.addEventListener("DOMContentLoaded", function () {
    // Handle Agenda Item Addition
    const agendaContainer = document.getElementById('agenda-container');
    const addAgendaBtn = document.getElementById('add-agenda-btn');

    addAgendaBtn.addEventListener('click', function () {
        const newAgendaInput = document.createElement('div');
        newAgendaInput.classList.add('col-12', 'mb-2');
        newAgendaInput.innerHTML = `<input type="text" class="form-control" name="agenda[]" placeholder="Agenda item ${agendaContainer.children.length + 1}" required />`;
        agendaContainer.appendChild(newAgendaInput);
    });

    // Handle Attendee Addition
    const attendeesContainer = document.getElementById('attendees-container');
    const addAttendeeBtn = document.getElementById('add-attendee-btn');

    addAttendeeBtn.addEventListener('click', function () {
        const newAttendeeInput = document.createElement('div');
        newAttendeeInput.classList.add('col-12', 'mb-2');
        newAttendeeInput.innerHTML = `<input type="text" class="form-control" name="attendees[]" placeholder="Attendee ${attendeesContainer.children.length + 1}" required />`;
        attendeesContainer.appendChild(newAttendeeInput);
    });

    // Handle Apology Addition
    const apologiesContainer = document.getElementById('apologies-container');
    const addApologyBtn = document.getElementById('add-apology-btn');

    addApologyBtn.addEventListener('click', function () {
        const newApologyInput = document.createElement('div');
        newApologyInput.classList.add('col-12', 'mb-2');
        newApologyInput.innerHTML = `<input type="text" class="form-control" name="apologies[]" placeholder="Apology ${apologiesContainer.children.length + 1}" required />`;
        apologiesContainer.appendChild(newApologyInput);
    });
});



document.addEventListener("DOMContentLoaded", function () {
    // Get references to the start time, end time, and duration input fields
    const startTimeInput = document.getElementById('start_time');
    const endTimeInput = document.getElementById('end_time');
    const durationInput = document.getElementById('duration');

    // Function to calculate duration
    function calculateDuration() {
        const startTime = startTimeInput.value;
        const endTime = endTimeInput.value;

        if (startTime && endTime) {
            const startParts = startTime.split(':');
            const endParts = endTime.split(':');

            // Convert start and end times to minutes
            const startMinutes = parseInt(startParts[0]) * 60 + parseInt(startParts[1]);
            const endMinutes = parseInt(endParts[0]) * 60 + parseInt(endParts[1]);

            let durationMinutes = endMinutes - startMinutes;

            // Adjust for cases where the end time is earlier than the start time (next day scenario)
            if (durationMinutes < 0) {
                durationMinutes += 24 * 60; // Add 24 hours worth of minutes
            }

            // Calculate hours and minutes
            const hours = Math.floor(durationMinutes / 60);
            const minutes = durationMinutes % 60;

            // Display the duration
            durationInput.value = `${hours} hours ${minutes} minutes`;
        }
    }

    // Event listeners to recalculate the duration when start or end time changes
    startTimeInput.addEventListener('change', calculateDuration);
    endTimeInput.addEventListener('change', calculateDuration);
});
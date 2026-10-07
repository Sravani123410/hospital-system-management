```javascript
// Hospital Management System JavaScript

document.addEventListener("DOMContentLoaded", function () {

    console.log("Hospital Management System loaded");

    // Delete confirmation
    const deleteForms = document.querySelectorAll(
        ".delete-form"
    );

    deleteForms.forEach(function (form) {

        form.addEventListener("submit", function (event) {

            const confirmed = confirm(
                "Are you sure you want to delete this record?"
            );

            if (!confirmed) {
                event.preventDefault();
            }

        });

    });


    // Automatically hide flash messages
    const alerts = document.querySelectorAll(
        ".alert"
    );

    alerts.forEach(function (alert) {

        setTimeout(function () {
            alert.style.display = "none";
        }, 5000);

    });

});
```

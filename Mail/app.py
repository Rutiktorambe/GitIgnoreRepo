
from flask import Flask, render_template_string, request

app = Flask(__name__)

EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>Reimbursement Email Preview</title>

<style>
* {
    box-sizing: border-box;
}

html, body {
    width: 100%;
    height: 100%;
    margin: 0;
    overflow: hidden;
    font-family: Arial, Helvetica, sans-serif;
    background: #f3f4f6;
    color: #333;
}

body {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px;
}

.email-card {
    width: 100%;
    max-width: 610px;
    max-height: calc(100dvh - 24px);
    background: white;
    border-radius: 7px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 2px 12px rgba(0,0,0,.06);
}

.accent {
    height: 4px;
    flex-shrink: 0;
    background: #d71920;
}

.content {
    padding: 17px 28px 12px;
    flex: 1;
    min-height: 0;
}

.logo {
    height: 29px;
    max-width: 145px;
    width: auto;
    object-fit: contain;
    object-position: left center;
    display: block;
}

.subtitle {
    font-size: 9px;
    color: #999;
    letter-spacing: 1px;
    margin-top: 3px;
}

h2 {
    font-size: 19px;
    margin: 19px 0 9px;
    color: #292929;
    font-weight: 600;
}

.intro {
    font-size: 12px;
    line-height: 1.5;
    color: #666;
    margin: 0 0 15px;
}

.reference {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 13px;
    background: #fff8f8;
    border-left: 3px solid #d71920;
    margin-bottom: 15px;
}

.reference-label {
    font-size: 11px;
    color: #777;
}

.reference-value {
    font-size: 14px;
    font-weight: bold;
    color: #d71920;
}

h3 {
    font-size: 13px;
    margin: 0 0 7px;
}

.details {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}

.details td {
    padding: 7px 4px;
    border-bottom: 1px solid #eeeeee;
}

.details td:first-child {
    color: #888;
    width: 40%;
}

.details td:last-child {
    color: #333;
    font-weight: 600;
}

.action {
    margin-top: 13px;
    padding: 10px 13px;
    background: #f8f8f8;
    border-left: 3px solid #d71920;
}

.action strong {
    font-size: 11px;
}

.action p {
    font-size: 11px;
    color: #666;
    line-height: 1.4;
    margin: 4px 0 0;
}

.closing {
    font-size: 11px;
    line-height: 1.45;
    margin-top: 13px;
    color: #555;
}

.closing strong {
    color: #333;
}

.footer {
    flex-shrink: 0;
    padding: 9px 28px;
    background: #fafafa;
    border-top: 1px solid #eee;
    color: #999;
    font-size: 9px;
    line-height: 1.4;
}

/* Compact layout for shorter laptop screens */
@media (max-height: 700px) {
    .content {
        padding: 12px 24px 9px;
    }

    .logo {
        height: 23px;
    }

    h2 {
        font-size: 17px;
        margin: 12px 0 7px;
    }

    .intro {
        font-size: 11px;
        margin-bottom: 10px;
    }

    .reference {
        padding: 7px 11px;
        margin-bottom: 10px;
    }

    .details td {
        padding: 5px 4px;
    }

    .action {
        margin-top: 9px;
        padding: 7px 11px;
    }

    .closing {
        margin-top: 9px;
    }

    .footer {
        padding: 7px 24px;
    }
}

/* Narrow screens */
@media (max-width: 480px) {
    body {
        padding: 7px;
    }

    .content {
        padding: 14px 16px 10px;
    }

    .footer {
        padding: 8px 16px;
    }

    h2 {
        font-size: 16px;
    }

    .reference-value {
        font-size: 12px;
    }
}
</style>
</head>

<body>

<div class="email-card">

    <div class="accent"></div>

    <main class="content">

        <!-- Company Logo -->
        <img
            src="{{ url_for('static', filename='intact-logo.png') }}"
            alt="Intact Insurance"
            class="logo"
        >

        <div class="subtitle">
            EMS | REIMBURSEMENT
        </div>

        <h2>Reimbursement Request Submitted</h2>

        <p class="intro">
            Dear Team,<br><br>
            A new employee reimbursement request has been
            successfully submitted through the EMS portal.
            Please find the request details below for your review.
        </p>

        <div class="reference">
            <span class="reference-label">Reference Number</span>
            <span class="reference-value">{{ reference }}</span>
        </div>

        <h3>Request Details</h3>

        <table class="details">
            <tr>
                <td>Employee Name</td>
                <td>{{ employee }}</td>
            </tr>

            <tr>
                <td>Reference Number</td>
                <td>{{ reference }}</td>
            </tr>

            <tr>
                <td>Submission Date</td>
                <td>{{ date }}</td>
            </tr>
        </table>

        <div class="action">
            <strong>Action Required</strong>
            <p>
                Kindly review the reimbursement request and take
                the necessary action as per the applicable
                reimbursement process.
            </p>
        </div>

        <div class="closing">
            Thank you for your attention and support.
            <br><br>
            Regards,<br>
            <strong>EMS Administration Team</strong><br>
            Intact
        </div>

    </main>

    <footer class="footer">
        Automated notification generated by the EMS
        Reimbursement System. Please do not reply directly.
    </footer>

</div>

</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def preview():

    employee = request.form.get(
        "employee", "Rutik Torambe"
    )

    reference = request.form.get(
        "reference", "EMS-2026-00125"
    )

    date = request.form.get(
        "date", "09-Nov-2026"
    )

    return render_template_string(
        EMAIL_TEMPLATE,
        employee=employee,
        reference=reference,
        date=date
    )


@app.route("/form")
def test_form():

    return """
    <!DOCTYPE html>
    <html>
    <body style="
        font-family:Arial;
        background:#f3f4f6;
        padding:30px;
    ">

    <div style="
        max-width:400px;
        margin:auto;
        background:white;
        padding:25px;
        border-radius:7px;
    ">

        <h2 style="color:#d71920;">Email Preview</h2>

        <form method="POST" action="/">

            Employee Name
            <input name="employee"
                value="Rutik Torambe"
                required
                style="width:100%;padding:10px;margin:8px 0 15px;">

            Reference Number
            <input name="reference"
                value="EMS-2026-00125"
                required
                style="width:100%;padding:10px;margin:8px 0 15px;">

            Submission Date
            <input name="date"
                value="09-Nov-2026"
                required
                style="width:100%;padding:10px;margin:8px 0 20px;">

            <button style="
                width:100%;
                padding:12px;
                background:#d71920;
                color:white;
                border:0;
                border-radius:4px;
                cursor:pointer;
            ">
                Preview Email
            </button>

        </form>
    </div>

    </body>
    </html>
    """


if __name__ == "__main__":
    app.run(debug=True, port=5000)

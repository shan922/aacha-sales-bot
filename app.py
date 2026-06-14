import os
import json
import re
from flask import Flask, request
import gspread
from google.oauth2.service_account import Credentials

# ---------------- ENV ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---------------- GOOGLE SHEETS ----------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

google_creds = json.loads(os.environ["GOOGLE_CREDENTIALS"])

CREDS = Credentials.from_service_account_info(
    google_creds,
    scopes=SCOPE
)

client = gspread.authorize(CREDS)

SHEET = client.open_by_key("1-jk1JIOQoR1uQU1UpnVlgXNrkcacvF8iViY46Vh7Sp8")
SALES_SHEET = SHEET.worksheet("sales")
PAYMENTS_SHEET = SHEET.worksheet("payments")

# ---------------- FLASK ----------------
app = Flask(__name__)

# ---------------- PARSER ----------------
def parse_message(text):
    data = {
        "date": None,
        "customer": "",
        "bike": "",
        "time": "",
        "days": "",
        "amount": 0,
        "status": "",
    }

    if not text:
        return data

    lines = text.split("\n")

    for line in lines:
        line = line.strip()

        if line.startswith("Date:"):
            data["date"] = line.replace("Date:", "").strip()

        elif line.startswith("Customer:"):
            data["customer"] = line.replace("Customer:", "").strip()

        elif line.startswith("Bike:"):
            data["bike"] = line.replace("Bike:", "").strip()

        elif line.startswith("Time:"):
            data["time"] = line.replace("Time:", "").strip()

        elif line.startswith("Taken for"):
            data["days"] = line.replace("Taken for", "").strip()

        elif line.startswith("Amount:"):
            match = re.findall(r"\d+", line)
            if match:
                data["amount"] = int(match[0])

        elif line.lower().startswith("paid"):
            data["status"] = "Paid"

        elif line.lower().startswith("unpaid"):
            data["status"] = "Unpaid"

    return data



# ---------------- SALES UPDATE ----------------
def update_sales(date_str, amount):
    try:
        if not date_str:
            return

        day = int(date_str.split("-")[2])

        col = day
        row = 2

        while SALES_SHEET.cell(row, col).value not in (None, ""):
            row += 1

        SALES_SHEET.update_cell(row, col, amount)

        print(f"Added {amount} to Day {day} Row {row}")

    except Exception as e:
        print("SALES ERROR:", e)


# ---------------- PAYMENT ADD ----------------
def add_payment(msg_id, data):
    try:
        PAYMENTS_SHEET.append_row([
            msg_id,
            data.get("date", ""),
            data.get("customer", ""),
            data.get("bike", ""),
            data.get("time", ""),
            data.get("days", ""),
            data.get("amount", 0),
            data.get("status", ""),
            data.get("days", "")
        ])

        print("PAYMENT ADDED")

    except Exception as e:
        print("PAYMENT ERROR:", e)


# ---------------- PAYMENT STATUS UPDATE ----------------
def update_payment_status(msg_id, status):
    try:
        records = PAYMENTS_SHEET.get_all_records()

        for i, row in enumerate(records):
            if str(row.get("Msg ID")) == str(msg_id):
                PAYMENTS_SHEET.update_cell(i + 2, 8, status)
                print("STATUS UPDATED")
                return

    except Exception as e:
        print("STATUS ERROR:", e)


# ---------------- WEBHOOK ----------------
@app.route("/", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        print("UPDATE RECEIVED")
        print(data)

        if not data:
            return "OK"

        message = data.get("message")
        edited = data.get("edited_message")

        msg = edited if edited else message

        if not msg:
            return "OK"

        text = msg.get("text", "")
        msg_id = msg.get("message_id")

        parsed = parse_message(text)

        if parsed["amount"]:
            update_sales(parsed["date"], parsed["amount"])
            add_payment(msg_id, parsed)

        if parsed["status"]:
            update_payment_status(msg_id, parsed["status"])

        return "OK"

    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return "OK"


# ---------------- START ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
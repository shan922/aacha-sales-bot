import os
import json
import re
import datetime
from flask import Flask, request
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ---------------- ENV ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---------------- GOOGLE SHEETS ----------------
SCOPE = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

google_creds = json.loads(os.environ["GOOGLE_CREDENTIALS"])

CREDS = Credentials.from_service_account_info(
    google_creds,
    scopes=SCOPE)
client = gspread.authorize(CREDS)

SHEET = client.open("AACHA RIDE SALES")
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
            data["amount"] = int(re.findall(r"\d+", line)[0])

        elif line.lower().startswith("paid"):
            data["status"] = "Paid"

        elif line.lower().startswith("unpaid"):
            data["status"] = "Unpaid"

    return data


# ---------------- SALES UPDATE ----------------
def update_sales(date_str, amount):
    day = int(date_str.split("-")[2])  # 1–31

    cell = SALES_SHEET.cell(2, day).value

    if cell == None or cell == "":
        cell = 0

    new_total = int(cell) + amount

    SALES_SHEET.update_cell(2, day, new_total)


# ---------------- PAYMENT UPDATE ----------------
def add_payment(msg_id, data):
    PAYMENTS_SHEET.append_row([
        msg_id,
        data["date"],
        data["customer"],
        data["bike"],
        data["time"],
        data["days"],
        data["amount"],
        data["status"],
        data["days"]
    ])


def update_payment_status(msg_id, status):
    records = PAYMENTS_SHEET.get_all_records()

    for i, row in enumerate(records):
        if str(row["Msg ID"]) == str(msg_id):
            PAYMENTS_SHEET.update_cell(i+2, 8, status)
            break


# ---------------- TELEGRAM HANDLER ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    msg_id = update.message.message_id

    data = parse_message(text)

    if not data["amount"]:
        return

    # UPDATE SALES
    update_sales(data["date"], data["amount"])

    # ADD PAYMENT RECORD
    add_payment(msg_id, data)


# ---------------- EDIT HANDLER ----------------
async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.edited_message:
        return

    text = update.edited_message.text
    msg_id = update.edited_message.message_id

    data = parse_message(text)

    if data["status"]:
        update_payment_status(msg_id, data["status"])


# ---------------- FLASK ROUTE ----------------
@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        data = request.get_json()

        print("UPDATE RECEIVED")
        print(data)

        update = Update.de_json(data, app_bot)
        app_bot.update_queue.put_nowait(update)

        return "OK"

    return "Bot Running"

# ---------------- START BOT ----------------
app_bot = Application.builder().token(BOT_TOKEN).build()

app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app_bot.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, handle_edit))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
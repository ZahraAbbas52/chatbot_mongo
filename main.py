from flask import Flask, request, jsonify
import requests
import os
import json
from rapidfuzz import process, fuzz
from collections import OrderedDict

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

GREEN_INSTANCE_ID = "7107376417"
GREEN_API_TOKEN = "e5808c2dca184e87868d28fe962121d5f6677825214646f893"
TENANT_ID = "68dfd3eceee9d45175067cbd"
BASE_URL = "https://backend-white-water-1093.fly.dev/api/chatbot"
HEADERS = {'token': 'cb_8a72e5f9b3d1c0e6'}
ALLOWED_NUMBERS = {"923032614853"}

def send_whatsapp_message(phone_number: str, text: str):
    url = f"https://api.green-api.com/waInstance{GREEN_INSTANCE_ID}/sendMessage/{GREEN_API_TOKEN}"
    payload = {"chatId": f"{phone_number}@c.us", "message": text}
    try:
        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            print(f" Message sent to {phone_number}")
        else:
            print(f" Failed to send message to {phone_number}: {resp.text}")
    except Exception as e:
        print(f" Error sending WhatsApp message: {e}")

def get_data(route: str, tenant_id: str):
    try:
        url = f"{BASE_URL}/{route}/{tenant_id}"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        print(f" Error fetching {route}: {e}")
        return []

def post_data(route: str, payload: dict):
    try:
        url = f"{BASE_URL}/{route}"
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        print(f" Error posting {route}: {e}")
        return []

def fuzzy_match(name: str, items: list, key: str = "name", threshold: int = 70):
    names = [i.get(key, "") for i in items]
    if not names:
        return None, 0

    result = process.extractOne(name, names, scorer=fuzz.token_sort_ratio)
    if not result:
        return None, 0

    best_name, score, _ = result
    matched_item = next(
        (i for i in items if i.get(key, "").lower() == best_name.lower()), None
    )

    if matched_item:
        matched_item["match_score"] = score
        return matched_item, score

    return None, score

def chat_logic(user_input: str, tenant: str):
    text_lower = user_input.lower().strip()

    if text_lower in ["hi", "hello", "hey", "salam", "assalamualaikum"]:
        return OrderedDict([
            ("bot", "Hello! I’m your assistant bot 👋"),
            ("commands", [
                "Type 'get all products' to see all products.",
                "Type 'get all clients' to see all clients.",
                "Type 'create invoice' to make a new invoice.",
                "Type 'get invoice by client' to fetch invoices of a client.",
                "Type 'get last 5 invoices' to fetch last 5 invoices."
            ])
        ])

    if "get all products" in text_lower:
        products = get_data("product", tenant)
        if not products:
            return {"bot": "No products found."}
        product_list = [
            OrderedDict([
                ("product_id", str(p.get("_id", ""))),
                ("name", p.get("name", "")),
                ("price", p.get("price", 0))
            ])
            for p in products
        ]
        return OrderedDict([
            ("bot", f"Found {len(product_list)} products."),
            ("products", product_list)
        ])

    if "get all clients" in text_lower:
        clients = get_data("client", tenant)
        if not clients:
            return {"bot": "No clients found."}
        client_list = [
            OrderedDict([
                ("client_id", str(c.get("_id", ""))),
                ("name", c.get("name", "")),
                ("email", c.get("email", "")),
                ("contact", c.get("contact", "")),
                ("address", c.get("address", ""))
            ])
            for c in clients
        ]
        return OrderedDict([
            ("bot", f"Found {len(client_list)} clients."),
            ("clients", client_list)
        ])

    if "create invoice" in text_lower:
        return {
            "bot": (
                "Please send invoice details in this format:\n\n"
                "ClientName\n"
                "Product1, Quantity, Price\n"
                "Product2, Quantity, Price"
            )
        }

    if "get last 5 invoices" in text_lower:
        invoices = get_data("quotation", tenant)
        invoices_sorted = sorted(invoices, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
        if not invoices_sorted:
            return {"bot": "No invoices found."}
        invoice_texts = [
            f"- Invoice: {inv.get('title')} | Client: {inv.get('client_name')} | Total: {inv.get('total_amount')}"
            for inv in invoices_sorted
        ]
        return {"bot": "Last 5 invoices:\n" + "\n".join(invoice_texts)}

    if "get invoice by client" in text_lower:
        clients = get_data("client", tenant)
        matched_client, score = fuzzy_match(user_input, clients, key="name", threshold=70)
        if not matched_client:
            return {"bot": "Please send the client name to get their invoices."}

        client_id = matched_client.get("_id")
        invoices = get_data("quotation", tenant)
        client_invoices = [inv for inv in invoices if inv.get("client_id") == client_id]
        if not client_invoices:
            return {"bot": f"No invoices found for client '{matched_client.get('name')}'."}

        invoice_texts = [
            f"- Invoice: {inv.get('title')} | Total Amount: {inv.get('total_amount')}"
            for inv in client_invoices
        ]
        return {"bot": f"Invoices for {matched_client.get('name')}:\n" + "\n".join(invoice_texts)}

    if "\n" in user_input:
        lines = [l.strip() for l in user_input.split("\n") if l.strip()]
        if not lines:
            return {"bot": "No details provided."}

        client_name = lines[0]
        clients = get_data("client", tenant)
        matched_client, client_score = fuzzy_match(client_name, clients, key="name", threshold=70)
        if not matched_client:
            return {"bot": f"No matching client found for '{client_name}'"}

        products = get_data("product", tenant)
        for p in products:
            p['name'] = f"{p.get('name', '')} {p.get('size', {}).get('name', '')}".strip().lower()

        items = []
        total_amount = 0.0

        for line in lines[1:]:
            try:
                product_name, quantity, price = [p.strip() for p in line.split(",")]
                quantity = int(quantity)
                price = float(price)

                matched_product, score = fuzzy_match(product_name, products, key="name", threshold=70)
                if matched_product:
                    item_type = "product" if score >= 70 else "service"

                    item_data = OrderedDict([
                        ("type", item_type),
                        ("product_id", matched_product.get("_id", "")),
                        ("product", matched_product.get("name", product_name)),
                        ("quantity", quantity),
                        ("price", price),
                        ("match_score", score)
                    ])

                    items.append(item_data)
                    total_amount += quantity * price

            except Exception as e:
                print(f" Error parsing line '{line}': {e}")

        if not items:
            return {"bot": "No valid products found. Please follow the format properly."}

        invoice_payload = OrderedDict([
            ("title", "created using WhatsApp"),
            ("user", "68dfd3eceee9d45175067cbb"),
            ("tenant", tenant),
            ("client_id", matched_client.get("_id", "")),
            ("client_name", matched_client.get("name", "")),
            ("client_match_score", client_score),
            ("items", items),
            ("total_amount", total_amount)
        ])

        post_data("quotation", invoice_payload)
        product_lines = [
            f"- {item['product']} (ID: {item.get('product_id', '')})\n  Qty: {item['quantity']} | Price: {item['price']} | Match: {item['match_score']}%"
            for item in items
        ]
        product_details_text = "\n".join(product_lines)
        bot_message = (
            f" Invoice created successfully!\n"
            f"Client: {matched_client.get('name', '')}\n\n"
            f" Product Details:\n{product_details_text}\n\n"
            f" Total Amount: {total_amount:.2f}"
        )

        return {"bot": bot_message, "invoice": invoice_payload}

    return {
        "bot": (
            "Sorry, I didn’t understand that.\n"
            "Please type one of these:\n"
            "- get all products\n"
            "- get all clients\n"
            "- create invoice\n"
            "- get invoice by client\n"
            "- get last 5 invoices"
        )
    }

@app.route("/chat", methods=["POST"])
def chat_route():
    data = request.get_json()
    user_input = data.get("text", "")
    tenant = data.get("tenant", TENANT_ID)
    return jsonify(chat_logic(user_input, tenant))

@app.route("/whatsapp_webhook", methods=["POST"])
def whatsapp_webhook():
    data = request.get_json()
    print("📩 Incoming WhatsApp data:", json.dumps(data, indent=4))

    raw_sender = data.get("senderData", {}).get("sender", "")
    sender_number = raw_sender.split("@")[0] if raw_sender else ""

    if sender_number not in ALLOWED_NUMBERS:
        print(f"⚠ Ignored message from {sender_number} (not allowed)")
        return jsonify({"status": "ignored", "reason": "not_allowed"})

    message_data = data.get("messageData", {})
    user_input = ""

    if "textMessageData" in message_data:
        user_input = message_data.get("textMessageData", {}).get("textMessage", "")
    elif "extendedTextMessageData" in message_data:
        user_input = message_data.get("extendedTextMessageData", {}).get("text", "")

    if not user_input:
        return jsonify({"status": "ignored", "reason": "no_message"})

    response = chat_logic(user_input, TENANT_ID)
    bot_text = response.get("bot", "Sorry, something went wrong.")
    print(f"💬 Replying to {sender_number}: {bot_text}")

    send_whatsapp_message(sender_number, bot_text)
    return jsonify({"status": "success", "reply_sent": bot_text})

@app.route("/hc", methods=["GET"])
def health_check():
    return jsonify({"message": " Server is running fine"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

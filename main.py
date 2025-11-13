from flask import Flask, request, jsonify
import requests, os, json
from rapidfuzz import process, fuzz
from collections import OrderedDict

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

TENANT_ID = "68dfd3eceee9d45175067cbd"
BASE_URL = "https://backend-white-water-1093.fly.dev/api/chatbot"
HEADERS = {'token': 'cb_8a72e5f9b3d1c0e6'}


def get_data(route: str, tenant_id: str):
    try:
        url = f"{BASE_URL}/{route}/{tenant_id}"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        print(f"Error fetching {route}: {e}")
        return []


def post_data(route: str, payload: dict):
    try:
        url = f"{BASE_URL}/{route}"
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        print(f"Error posting {route}: {e}")
        return []


def fuzzy_match(name: str, items: list, key: str = "name", threshold: int = 70):
    names = [i.get(key, "") for i in items]
    if not names:
        return None, 0
    result = process.extractOne(name, names, scorer=fuzz.token_sort_ratio)
    if not result:
        return None, 0
    best_name, score, _ = result
    matched_item = next((i for i in items if i.get(key, "").lower() == best_name.lower()), None)
    if matched_item:
        matched_item["match_score"] = score
        return matched_item, score
    return None, score


def handle_greeting():
    return jsonify(OrderedDict([
        ("bot", "Hello! I’m your assistant bot."),
        ("commands", [
            "Type 'get all products' to see all products.",
            "Type 'get all clients' to see all clients.",
            "Type 'create invoice' to make a new invoice.",
            "Type 'get invoice by client: ClientName' to fetch invoices.",
            "Type 'get last 5 invoices' to fetch last 5 invoices."
        ])
    ]))


def handle_get_all_products(tenant):
    products = get_data("product", tenant)
    if not products:
        return jsonify({"bot": "No products found."})

    product_list = [
        OrderedDict([
            ("name", p.get("name", "")),
            ("product_id", str(p.get("_id", ""))),
            ("price", p.get("price", 0))
        ]) for p in products
    ]
    return jsonify(OrderedDict([
        ("bot", f"Found {len(product_list)} products."),
        ("products", product_list)
    ]))


def handle_get_all_clients(tenant):
    clients = get_data("client", tenant)
    if not clients:
        return jsonify({"bot": "No clients found."})
    client_list = [
        OrderedDict([
            ("name", c.get("name", "")),
            ("client_id", str(c.get("_id", "")))
        ]) for c in clients
    ]
    return jsonify(OrderedDict([
        ("bot", f"Found {len(client_list)} clients."),
        ("clients", client_list)
    ]))


def handle_create_invoice_prompt():
    return jsonify({
        "bot": (
            "Please send invoice details in this format:\n\n"
            "ClientName\n"
            "Product1, Quantity, Price\n"
            "Product2, Quantity, Price"
        )
    })


def handle_get_last_invoices(tenant):
    invoices = get_data("quotation", tenant)
    invoices_sorted = sorted(invoices, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
    if not invoices_sorted:
        return jsonify({"bot": "No invoices found."})

    invoice_texts = [
        f"- Invoice: {inv.get('title')} | Client: {inv.get('client_name')} | Total: {inv.get('total_amount')}"
        for inv in invoices_sorted
    ]
    return jsonify({"bot": "Last 5 invoices:\n" + "\n".join(invoice_texts)})


def handle_get_invoice_by_client(client_name, tenant):
    clients = get_data("client", tenant)
    matched_client, score = fuzzy_match(client_name, clients, key="name", threshold=70)
    if not matched_client:
        return jsonify({"bot": f"No matching client found for '{client_name}'"})

    invoices = get_data("quotation", tenant)
    client_invoices = [inv for inv in invoices if inv.get("client_id") == matched_client.get("_id")]
    if not client_invoices:
        return jsonify({"bot": f"No invoices found for client '{matched_client.get('name')}'."})

    invoice_texts = [
        f"- Invoice: {inv.get('title')} | Total Amount: {inv.get('total_amount')}"
        for inv in client_invoices
    ]
    return jsonify({"bot": f"Invoices for {matched_client.get('name')}:\n" + "\n".join(invoice_texts)})


def handle_create_invoice_from_text(user_input, tenant):
    lines = [l.strip() for l in user_input.split("\n") if l.strip()]
    if not lines:
        return jsonify({"bot": "No details provided."})

    client_name = lines[0]
    clients = get_data("client", tenant)
    matched_client, client_score = fuzzy_match(client_name, clients, key="name", threshold=70)
    if not matched_client:
        return jsonify({"bot": f"No matching client found for '{client_name}'"})

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
            print(f"Error parsing line '{line}': {e}")

    if not items:
        return jsonify({"bot": "No valid products found. Please follow the format properly."})

    invoice_payload = OrderedDict([
        ("title", "created using Postman"),
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
    bot_message = (
        f"Invoice created successfully!\n"
        f"Client: {matched_client.get('name', '')}\n\n"
        f"Product Details:\n" + "\n".join(product_lines) +
        f"\n\nTotal Amount: {total_amount:.2f}"
    )
    return jsonify({"bot": bot_message, "invoice": invoice_payload})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_input = data.get("text", "").strip()
    tenant = data.get("tenant", TENANT_ID)
    text_lower = user_input.lower()

    if text_lower in ["hi", "hello", "hey", "salam", "assalamualaikum"]:
        return handle_greeting()

    elif "get all products" in text_lower:
        return handle_get_all_products(tenant)

    elif "get all clients" in text_lower:
        return handle_get_all_clients(tenant)

    elif "create invoice" in text_lower:
        return handle_create_invoice_prompt()

    elif "get last 5 invoices" in text_lower:
        return handle_get_last_invoices(tenant)

    elif text_lower.startswith("get invoice by client:"):
        client_name = user_input.split(":", 1)[1].strip()
        return handle_get_invoice_by_client(client_name, tenant)

    elif "\n" in user_input:
        return handle_create_invoice_from_text(user_input, tenant)

    return jsonify({
        "bot": (
            "Sorry, I didn’t understand that.\n"
            "Please type one of these:\n"
            "- get all products\n"
            "- get all clients\n"
            "- create invoice\n"
            "- get invoice by client: ClientName\n"
            "- get last 5 invoices"
        )
    })


@app.route("/hc", methods=["GET"])
def health_check():
    return jsonify({"message": "Server is running fine"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

import requests
from rapidfuzz import process, fuzz
from collections import OrderedDict
from constants import BASE_URL, HEADERS, INTENT_PATTERNS

def api_request(method, route, tenant=None, payload=None):
    try:
        url = f"{BASE_URL}/{route}"
        if tenant:
            url = f"{url}/{tenant}"

        if method == "GET":
            response = requests.get(url, headers=HEADERS)
        else:
            response = requests.post(url, headers=HEADERS, json=payload)

        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        print(f"API Error ({method} {route}): {e}")
        return []


def get_data(route, tenant):
    return api_request("GET", route, tenant)


def post_data(route, payload):
    return api_request("POST", route, payload=payload)

def fuzzy_match(query, items, key="name", threshold=70):
    names = [i.get(key, "") for i in items]
    if not names:
        return None, 0

    result = process.extractOne(query, names, scorer=fuzz.token_sort_ratio)
    if not result:
        return None, 0

    best_name, score, _ = result
    matched_item = next((i for i in items if i.get(key, "").lower() == best_name.lower()), None)

    if score >= threshold and matched_item:
        matched_item["match_score"] = score
        return matched_item, score

    return None, score

def parse_invoice_text(user_input):
    lines = [l.strip() for l in user_input.split("\n") if l.strip()]
    if not lines:
        return None, None

    return lines[0], lines[1:]  

def make_list_response(label, items, key_map):
    formatted = [
        OrderedDict([(new_key, item.get(old_key, "")) for new_key, old_key in key_map.items()])
        for item in items
    ]
    return OrderedDict([
        ("bot", f"Found {len(formatted)} {label}."),
        (label, formatted),
    ])


def handle_get_all_products(tenant):
    products = get_data("product", tenant)
    if not products:
        return {"bot": "No products found."}

    return make_list_response("products", products, {
        "name": "name",
        "product_id": "_id",
        "price": "price"
    })


def handle_get_all_clients(tenant):
    clients = get_data("client", tenant)
    if not clients:
        return {"bot": "No clients found."}

    return make_list_response("clients", clients, {
        "name": "name",
        "client_id": "_id"
    })

def handle_create_invoice_prompt():
    return {
        "bot": (
            "Please send invoice details:\n\n"
            "ClientName\n"
            "Product1, Quantity, Price\n"
            "Product2, Quantity, Price"
        )
    }


def handle_get_last_invoices(tenant):
    clients = get_data("client", tenant)
    client_map = {c.get("_id"): c.get("name") for c in clients}

    invoices = api_request("GET", "invoices", tenant)
    if not invoices:
        return {"bot": "No invoices found."}

    formatted = []
    for idx, inv in enumerate(invoices[:5], start=1):
        cid = inv.get("client")
        formatted.append(OrderedDict([
            ("sequence", idx),
            ("client_name", client_map.get(cid, "")),
            ("client_id", cid),
            ("date", inv.get("date") or inv.get("createdAt")),
            ("totalAmount", inv.get("totalAmount", 0)),
            ("amountReceived", inv.get("amountReceived", 0)),
            ("paymentStatus", inv.get("paymentStatus", "")),
        ]))

    return OrderedDict([
        ("bot", "Last 5 invoices:"),
        ("invoices", formatted),
    ])


def handle_get_invoice_by_client(client_name, tenant):
    clients = get_data("client", tenant)
    matched_client, _ = fuzzy_match(client_name, clients)
    if not matched_client:
        return {"bot": f"No matching client found for '{client_name}'"}

    cid = matched_client.get("_id")
    invoices = api_request("GET", f"invoices/{cid}", tenant)
    if not invoices:
        return {"bot": f"No invoices found for '{matched_client.get('name')}'."}

    result = []
    for idx, inv in enumerate(invoices, start=1):
        result.append({
            "sequence": idx,
            "invoice_title": inv.get("title", ""),
            "date": inv.get("date") or inv.get("createdAt", ""),
            "totalAmount": inv.get("totalAmount", 0),
            "paymentStatus": inv.get("paymentStatus", ""),
        })

    return {"bot": f"Invoices for {matched_client.get('name')}:", "invoices": result}


def build_invoice_payload(client_name, item_lines, tenant):
    clients = get_data("client", tenant)
    matched_client, score = fuzzy_match(client_name, clients)
    if not matched_client:
        return None, {"bot": f"No matching client found for '{client_name}'"}

    products = get_data("product", tenant)
    for p in products:
        full_name = f"{p.get('name', '')} {p.get('size', {}).get('name', '')}".strip()
        p["full_name"] = full_name.lower()

    items = []
    total_amount = 0

    for line in item_lines:
        try:
            product_name, qty, price = [x.strip() for x in line.split(",")]
            qty = int(qty)
            price = float(price)

            matched_product, score = fuzzy_match(product_name.lower(), products, key="full_name")

            if matched_product:
                items.append({
                    "type": "product",
                    "product_id": matched_product.get("_id"),
                    "product": matched_product.get("full_name"),
                    "quantity": qty,
                    "price": price,
                    "match_score": score
                })
                total_amount += qty * price

        except:
            continue

    if not items:
        return None, {"bot": "No valid products found. Please check your format."}

    return OrderedDict([
        ("title", "created using Whatsapp"),
        ("tenant", tenant),
        ("client_id", matched_client.get("_id")),
        ("client_match_score", score),
        ("items", items),
        ("total_amount", total_amount)
    ]), None



def create_invoice_on_server(payload):
    if not payload:
        return False, {"bot": "Invalid payload."}

    success = post_data("quotation", payload)
    if not success:
        return False, {"bot": "Error creating invoice."}

    return True, None



def handle_create_invoice_from_text(user_input, tenant):
    client_name, item_lines = parse_invoice_text(user_input)
    if not client_name:
        return {"bot": "Invalid format."}

    payload, error = build_invoice_payload(client_name, item_lines, tenant)
    if error:
        return error

    success, error = create_invoice_on_server(payload)
    if error:
        return error

    return {"bot": "Invoice created successfully!", "invoice": payload}

def parse_intent(text):
    text = text.lower().strip()

    for intent, patterns in INTENT_PATTERNS.items():
        for p in patterns:
            if p in text:
                return {"intent": intent}

    return {"intent": None}

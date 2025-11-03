from flask import Flask, request, jsonify
import requests
from rapidfuzz import fuzz, process
from collections import OrderedDict
import json

tenant = "68dfd3eceee9d45175067cbd"

app = Flask(__name__)

app.config["JSON_SORT_KEYS"] = False

BASE_URL = "https://backend-white-water-1093.fly.dev/api/chatbot"

def get_data(route, tenantId):
    try:
        url = f"{BASE_URL}/{route}/{tenantId}"
        payload = {}
        headers = { 'token': 'cb_8a72e5f9b3d1c0e6' }
        response = requests.request("GET", url, headers=headers, data=payload)
        response.raise_for_status()
        return response.json()['data']
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {route}: {e}")
        return []


def find_best_match(tenant, name, data_type, field="name", threshold=20):

    if data_type == "product":
        all_items = get_data("product", tenant)
        for item in all_items:
            size_name = item.get("size", {}).get("name", "")
            item["name"] = f"{item['name']} {size_name}".strip().lower()
    else:
        all_items = get_data("client", tenant)

    names = [item[field].lower() for item in all_items if field in item]
    if not names:
        return None, 0

    best_match, score, _ = process.extractOne(name, names, scorer=fuzz.token_sort_ratio)

    if score >= threshold:
        for item in all_items:
            if item[field].lower() == best_match.lower():
                item["match_score"] = score
                return item, score
    return None, score

@app.route("/test", methods=["POST"])
def post():
    data = request.get_json()
    text = data.get("text", "")
    tenant = data['tenant']

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return jsonify({"error": "No input text provided"}), 400

    client_name = lines[0]
    client, client_score = find_best_match(tenant, client_name, "client")

    if not client:
        return jsonify({"error": f"No client found similar to '{client_name}'"}), 404

    products = []
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue

        product_name, qty, price = parts[0], parts[1], parts[2]
        product, score = find_best_match(tenant, product_name.lower(), "product")

        if product:
            product_obj = OrderedDict([
                ("product_id", str(product.get("_id", ""))),
                ("product_name", product.get("name", "")),
                ("quantity", int(qty)),
                ("price", float(price)),
                ("match_score", score)
            ])
        else:
            product_obj = OrderedDict([
                ("product_name", product_name),
                ("quantity", int(qty)),
                ("price", float(price)),
                ("error", "No close match found"),
                ("match_score", score)
            ])
        products.append(product_obj)

    response = OrderedDict([
        ("client", OrderedDict([
            ("client_id", str(client.get("_id", ""))),
            ("client_name", client.get("name")),
            ("match_score", client_score)
        ])),
        ("products", products)
    ])

    return app.response_class(
        response=json.dumps(response, indent=4),
        mimetype="application/json"
    )


app.run()

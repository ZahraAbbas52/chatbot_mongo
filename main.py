from flask import Flask, request, jsonify
import requests
from rapidfuzz import fuzz, process
from collections import OrderedDict
import json
import os

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

BASE_URL = "https://backend-white-water-1093.fly.dev/api/chatbot"


def get_data(route, tenant_id):
    try:
        url = f"{BASE_URL}/{route}/{tenant_id}"
        headers = {'token': 'cb_8a72e5f9b3d1c0e6'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get('data', [])
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

    best_match, score, _ = process.extractOne(name.lower(), names, scorer=fuzz.token_sort_ratio)

    if score >= threshold:
        for item in all_items:
            if item[field].lower() == best_match.lower():
                item["match_score"] = score
                return item, score
    return None, score


@app.route("/test", methods=["POST"])
def post():
    data = request.get_json()
    text = data.get("text", "").strip()
    tenant = data.get("tenant")

    if not tenant:
        return jsonify({"error": "Missing tenant ID"}), 400

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

    return jsonify(response)


@app.route('/hc', methods=['GET'])
def health_check():
    return jsonify({"message": "Server is running fine"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

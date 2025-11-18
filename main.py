import os
from flask import Flask, request, jsonify
from intent_engine import parse_intent
from catalog_service import handle_get_all_clients, handle_get_all_products
from invoice_service import (
    handle_create_invoice_from_text,
    handle_create_invoice_prompt,
    handle_get_invoice_by_client,
    handle_get_last_invoices
)

from constants import TENANT_ID, GREETINGS

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_input = data.get("text", "").strip()
    tenant = data.get("tenant", TENANT_ID)

    intent = parse_intent(user_input)["intent"]

    if intent == "greet":
        return jsonify(GREETINGS)

    elif intent == "get_all_products":
        return handle_get_all_products(tenant)

    elif intent == "get_all_clients":
        return handle_get_all_clients(tenant)

    elif intent == "create_invoice_prompt":
        return handle_create_invoice_prompt()

    elif intent == "get_last_5_invoices":
        return handle_get_last_invoices(tenant)

    elif intent == "get_invoice_by_client":
        if ":" in user_input:
            client_name = user_input.split(":", 1)[1].strip()
            return handle_get_invoice_by_client(client_name, tenant)
        return {"bot": "Please write like: get invoice by client: ClientName"}

    elif intent == "invoice_text":
        return handle_create_invoice_from_text(user_input, tenant)

    else:
        return jsonify({
            "bot": (
                "Sorry, I didn’t understand that.\nTry:\n"
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

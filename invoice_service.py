from collections import OrderedDict
import requests   # FIXED
from constants import BASE_URL, HEADERS   # FIXED

from utils import (
    get_data,
    fuzzy_match,
    post_data,
    parse_invoice_text,
    build_invoice_payload,
    create_invoice_on_server
)


def handle_create_invoice_prompt():
    return {
        "bot": (
            "Please send invoice details in this format:\n\n"
            "ClientName\n"
            "Product1, Quantity, Price\n"
            "Product2, Quantity, Price"
        )
    }


def handle_get_last_invoices(tenant):
    clients = get_data("client", tenant)
    client_map = {c.get("_id"): c.get("name", "") for c in clients}

    try:
        url = f"{BASE_URL}/invoices/{tenant}?last=5"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json().get("data", [])
    except:
        return {"bot": "Error fetching invoices from server."}

    if not data:
        return {"bot": "No invoices found."}

    invoice_list = []
    for idx, inv in enumerate(data, start=1):
        client_id = inv.get("client", "")
        invoice_list.append(OrderedDict([
            ("sequence", idx),
            ("client_name", client_map.get(client_id, "")),
            ("client_id", client_id),
            ("date", inv.get("date") or inv.get("createdAt", "")),
            ("totalAmount", inv.get("totalAmount", 0)),
            ("amountReceived", inv.get("amountReceived", 0)),
            ("paymentStatus", inv.get("paymentStatus", ""))
        ]))

    return OrderedDict([
        ("bot", "Last 5 invoices:"),
        ("invoices", invoice_list)
    ])


def handle_get_invoice_by_client(client_name, tenant):
    clients = get_data("client", tenant)
    matched_client, score = fuzzy_match(client_name, clients, key="name")

    if not matched_client:
        return {"bot": f"No matching client found for '{client_name}'"}

    client_id = matched_client.get("_id")

    try:
        url = f"{BASE_URL}/invoices/{tenant}/{client_id}"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        invoices = response.json().get("data", [])
    except:
        return {"bot": "Error fetching client invoices from server."}

    if not invoices:
        return {"bot": f"No invoices found for client '{matched_client.get('name')}'."}

    invoice_list = []
    for idx, inv in enumerate(invoices, start=1):
        invoice_list.append({
            "sequence": idx,
            "invoice_title": inv.get("title", ""),
            "date": inv.get("date") or inv.get("createdAt", ""),
            "totalAmount": inv.get("totalAmount", 0),
            "paymentStatus": inv.get("paymentStatus", "")
        })

    return {
        "bot": f"Invoices for {matched_client.get('name')}:",
        "invoices": invoice_list
    }


def handle_create_invoice_from_text(user_input, tenant):
    client_name, item_lines = parse_invoice_text(user_input)

    if not client_name:
        return {"bot": "No details provided."}

    payload, error = build_invoice_payload(client_name, item_lines, tenant)
    if error:
        return error

    success, error = create_invoice_on_server(payload)
    if error:
        return error

    return {"bot": "Invoice created successfully!", "invoice": payload}

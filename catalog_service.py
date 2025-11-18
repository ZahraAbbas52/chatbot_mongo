from collections import OrderedDict
from utils import get_data


def handle_get_all_products(tenant):
    products = get_data("product", tenant)
    if not products:
        return {"bot": "No products found."}

    product_list = [
        OrderedDict([
            ("name", p.get("name", "")),
            ("product_id", str(p.get("_id", ""))),
            ("price", p.get("price", 0))
        ]) for p in products
    ]

    return OrderedDict([
        ("bot", f"Found {len(product_list)} products."),
        ("products", product_list)
    ])


def handle_get_all_clients(tenant):
    clients = get_data("client", tenant)
    if not clients:
        return {"bot": "No clients found."}

    client_list = [
        OrderedDict([
            ("name", c.get("name", "")),
            ("client_id", str(c.get("_id", "")))
        ]) for c in clients
    ]

    return OrderedDict([
        ("bot", f"Found {len(client_list)} clients."),
        ("clients", client_list)
    ])

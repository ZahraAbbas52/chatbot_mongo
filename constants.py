from collections import OrderedDict

TENANT_ID = "68dfd3eceee9d45175067cbd"
BASE_URL = "https://backend-white-water-1093.fly.dev/api/chatbot"
HEADERS = {'token': 'cb_8a72e5f9b3d1c0e6'}

GREETINGS = OrderedDict([
        ("bot", "Hello! I’m your assistant bot."),
        ("commands", [
            "Type 'get all products' to see all products.",
            "Type 'get all clients' to see all clients.",
            "Type 'create invoice' to make a new invoice.",
            "Type 'get invoice by client: ClientName' to fetch invoices.",
            "Type 'get last 5 invoices' to fetch last 5 invoices."
        ])
    ])


INTENT_PATTERNS = {
    "greet": ["hi", "hello", "hey", "salam", "assalamualaikum"],
    "get_all_products": ["get all products", "show products", "products list"],
    "get_all_clients": ["get all clients", "show clients", "clients list"],
    "create_invoice_prompt": ["create invoice", "make invoice", "new invoice"],
    "get_last_5_invoices": ["get last 5 invoices", "recent invoices", "last invoices"],
    "get_invoice_by_client": ["get invoice by client", "invoice by client", "client invoice"],
}
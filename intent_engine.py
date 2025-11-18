from constants import INTENT_PATTERNS


def parse_intent(user_input: str):
    text = user_input.lower()

    for intent, patterns in INTENT_PATTERNS.items():
        for p in patterns:
            if p in text:
                return {"intent": intent}

    if "\n" in user_input:
        return {"intent": "invoice_text"}

    return {"intent": "unknown"}

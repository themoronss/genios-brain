def parse_email_headers(headers):
    data = {}

    for h in headers:
        if h["name"] == "From":
            data["from"] = h["value"]
        if h["name"] == "Subject":
            data["subject"] = h["value"]
        if h["name"] == "Date":
            data["date"] = h["value"]

    return data
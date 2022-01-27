import requests
from flask import request
from functools import wraps


def send_telegram_message(token: str, message: str, id: str):
    return requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        {"chat_id": id, "parse_mode": "Markdown", "text": message},
    ).status_code


def get_ms_id(token: str):
    return requests.get(
        "https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"{token}"}
    ).json()


def validate_id(function):
    @wraps(function)
    def wrap_function(*args, **kwargs):
        try:
            ms_id = get_ms_id(request.headers["Authorization"])["id"]
        except KeyError:
            return "No valid token present", 401

        return function(ms_id, *args, **kwargs)

    return wrap_function


def validate_id_with_name(function):
    @wraps(function)
    def wrap_function(*args, **kwargs):
        try:
            user = get_ms_id(request.headers["Authorization"])
            ms_id = user["id"]
            name = user["givenName"]
        except KeyError:
            return "No valid token present", 401

        return function(ms_id, name, *args, **kwargs)

    return wrap_function


def validate_id_with_username(function):
    @wraps(function)
    def wrap_function(*args, **kwargs):
        try:
            user = get_ms_id(request.headers["Authorization"])
            ms_id = user["id"]
            username = user["userPrincipalName"]
        except KeyError:
            return "No valid token present", 401

        return function(ms_id, username, *args, **kwargs)

    return wrap_function


def parse_table(text: str, ignore_split: bool = False) -> dict:
    table = {}

    for line in text.splitlines():
        if not line or line[0] == "#":
            continue
        col = line.split()
        table[col[0]] = col[1 :: 2 if ignore_split else 1]

    return table


def get_pwr_supply_table(host: str = "10.0.38.46") -> dict:
    udc_ps = parse_table(
        requests.get(f"http://{host}/control-system-constants/beaglebone/udc-bsmp.txt").text, True
    )
    bbb_udc = parse_table(
        requests.get(f"http://{host}/control-system-constants/beaglebone/beaglebone-udc.txt").text
    )
    ip_bbb = parse_table(
        requests.get(f"http://{host}/control-system-constants/beaglebone/ip-list.txt").text
    )

    final_map = {}

    for bbb, udcs in bbb_udc.items():
        pwr_supplies = []
        for udc in udcs:
            pwr_supplies += udc_ps[udc]

        final_map[ip_bbb[bbb][0]] = {"ps": pwr_supplies, "udc": udcs}

    return final_map

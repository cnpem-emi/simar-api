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
            ms_id = get_ms_id(request.headers["Authorization"])["id"]
            name = get_ms_id(request.headers["Authorization"])["givenName"]
        except KeyError:
            return "No valid token present", 401

        return function(ms_id, name, *args, **kwargs)

    return wrap_function


def validate_id_with_username(function):
    @wraps(function)
    def wrap_function(*args, **kwargs):
        try:
            ms_id = get_ms_id(request.headers["Authorization"])["id"]
            username = get_ms_id(request.headers["Authorization"])["userPrincipalName"]
        except KeyError:
            return "No valid token present", 401

        return function(ms_id, username, *args, **kwargs)

    return wrap_function

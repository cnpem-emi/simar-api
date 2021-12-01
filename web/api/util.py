import requests
from flask import request
from functools import wraps


def get_ms_id(token: str):
    return requests.get(
        "https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"{token}"}
    ).json()["id"]


def validate_id(function):
    @wraps(function)
    def wrap_function(*args, **kwargs):
        try:
            ms_id = get_ms_id(request.headers["Authorization"])
        except KeyError:
            return "No valid token present", 401

        return function(ms_id, *args, **kwargs)

    return wrap_function

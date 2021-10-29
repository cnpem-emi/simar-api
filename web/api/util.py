import requests


def get_ms_id(token: str):
    return requests.get(
        "https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"{token}"}
    ).json()["id"]

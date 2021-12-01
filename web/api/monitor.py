import json
from pywebpush import WebPushException, webpush
from api.models import User
from api.templates import (
    telegram_warning_high,
    telegram_warning_low,
    push_warning_low,
    push_warning_high,
)
from api.util import send_telegram_message
from epics import caget
from time import sleep


def main_loop(private_key, claims, telegram_token):
    while True:
        pv_cache = {}
        for user in User.objects():
            message, last_pv, t_message = "", "", ""
            warning_count = 0
            for pv in user.pvs:
                if not pv.subbed:
                    continue
                if pv.name not in pv_cache:
                    pv_cache[pv.name] = {
                        "value": caget(pv.name, timeout=2),
                        "egu": caget(pv.name + ".EGU", timeout=2),
                    }

                if pv.hi_limit < pv_cache[pv.name]["value"]:
                    message = push_warning_high.safe_substitute(
                        PV=pv.name,
                        LIMIT=pv.hi_limit,
                        EGU=pv_cache[pv.name]["egu"],
                        VALUE=pv_cache[pv.name]["value"],
                    )
                    t_message += telegram_warning_high.safe_substitute(
                        PV=pv.name,
                        LIMIT=pv.hi_limit,
                        EGU=pv_cache[pv.name]["egu"],
                        VALUE=pv_cache[pv.name]["value"],
                    )
                elif pv.lo_limit > pv_cache[pv.name]["value"]:
                    message = message = push_warning_low.safe_substitute(
                        PV=pv.name,
                        LIMIT=pv.hi_limit,
                        EGU=pv_cache[pv.name]["egu"],
                        VALUE=pv_cache[pv.name]["value"],
                    )
                    t_message += telegram_warning_low.safe_substitute(
                        PV=pv.name,
                        LIMIT=pv.hi_limit,
                        EGU=pv_cache[pv.name]["egu"],
                        VALUE=pv_cache[pv.name]["value"],
                    )
                else:
                    continue

                warning_count += 1
                last_pv = pv.name

            if message:
                if warning_count > 1:
                    message = f"{last_pv} and {warning_count - 1} other PV{'s' if warning_count - 2 > 0 else ''} have violated their limits"  # noqa: E501

                if user.telegram_id:
                    send_telegram_message(telegram_token, t_message, user.telegram_id)

                data = {
                    "title": "PV Limit Violation",
                    "body": message,
                    "url": "https://10.0.6.75:8085",
                }

                for device in user.devices:
                    try:
                        sub = json.dumps(
                            {
                                "endpoint": device.endpoint,
                                "keys": {
                                    "auth": device.auth,
                                    "p256dh": device.p256dh,
                                },
                            }
                        )
                        webpush(
                            subscription_info=json.loads(sub),
                            data=json.dumps(data),
                            vapid_private_key=private_key,
                            vapid_claims=claims,
                        )
                    except WebPushException as e:
                        print(e.response.json())
        sleep(120)

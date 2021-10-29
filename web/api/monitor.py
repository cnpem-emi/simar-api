import json
from pywebpush import WebPushException, webpush
from api.models import User
from epics import caget
from time import sleep


def main_loop(private_key, claims):
    while True:
        pv_cache = {}
        for user in User.objects():
            message, last_pv = "", ""
            warning_count = 0
            for pv in user.subbed_pvs:
                if pv.name not in pv_cache:
                    pv_cache[pv.name] = caget(pv.name, timeout=2)

                if pv.hi_limit < pv_cache[pv.name]:
                    message = f"{pv.name} has surpassed {pv.hi_limit} (Current value: {pv_cache[pv.name]})"
                elif pv.lo_limit > pv_cache[pv.name]:
                    message = f"{pv.name} has gone below {pv.lo_limit} (Current value: {pv_cache[pv.name]})"
                else:
                    continue

                warning_count += 1
                last_pv = pv.name

            if message:
                if warning_count > 1:
                    message = f"{last_pv} and {warning_count - 1} other PV{'s' if warning_count - 2 > 0 else ''} have violated their limits"  # noqa: E501

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
        sleep(60)

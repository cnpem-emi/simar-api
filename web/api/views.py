import json
from redis import Redis

from api.util import (
    send_telegram_message,
    validate_id,
    validate_id_with_name,
    validate_id_with_username,
)
from flask import jsonify, request, current_app, Blueprint
from api.models import Pv, User, Device
from api.templates import hello
from pywebpush import webpush, WebPushException

redis_server = Redis(host="redis-db", port=6379)
bp = Blueprint("simar", __name__)


@bp.get("/get_subscriptions")
@validate_id
def get_subs(ms_id):
    return jsonify([pv.name for pv in User.objects(ms_id=ms_id, pvs__subbed=True)[0].pvs]), 200


@bp.get("/get_pvs")
@validate_id
def get_pvs(ms_id):
    try:
        return jsonify([pv.to_mongo() for pv in User.objects(ms_id=ms_id)[0].pvs]), 200
    except Exception:
        return "User not found", 404


@bp.post("/subscribe")
@validate_id
def subscribe(ms_id):
    r_json = request.json
    sub = r_json.get("sub")

    if not r_json.get("pvs"):
        return "Bad Request", 400

    device = Device(
        endpoint=sub.get("endpoint"),
        auth=sub.get("keys").get("auth"),
        p256dh=sub.get("keys").get("p256dh"),
    )

    for pv in r_json.get("pvs"):
        new_pv = Pv(
            name=pv.get("name"),
            hi_limit=pv.get("hi_limit") or 500,
            lo_limit=pv.get("lo_limit") or 0,
            subbed=True,
        )

        update = User.objects(ms_id=ms_id, pvs__name=pv.get("name")).update_one(
            add_to_set__devices=device,
            set__pvs__S__subbed=True,
        )

        if not update:
            User.objects(ms_id=ms_id).update_one(
                add_to_set__pvs=new_pv,
                add_to_set__devices=device,
                upsert=True,
            )

    return jsonify(r_json.get("pvs")), 200


@bp.post("/unsubscribe")
@validate_id
def unsubscribe(ms_id):
    if not request.json.get("pvs"):
        return "Bad Request", 400

    for pv in request.json.get("pvs"):
        User.objects(ms_id=ms_id, pvs__name=pv).update(set__pvs__S__subbed=False)

    return jsonify(request.json.get("pvs")), 200


@bp.delete("/unsubscribe_all")
@validate_id
def unsubscribe_all(ms_id):
    User.objects(ms_id=ms_id).delete()
    return "OK", 200


@bp.post("/notify")
@validate_id
def notify(ms_id):
    count = 0

    data = {
        "title": request.json.get("title"),
        "body": request.json.get("body"),
        "url": request.json.get("url"),
    }

    for device in User.objects(ms_id=ms_id)[0].devices:
        try:
            sub = json.dumps(
                {
                    "endpoint": device.endpoint,
                    "keys": {"auth": device.auth, "p256dh": device.p256dh},
                }
            )
            webpush(
                subscription_info=json.loads(sub),
                data=json.dumps(data),
                vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
                vapid_claims=current_app.config["VAPID_CLAIMS"],
            )
            count += 1
        except WebPushException as e:
            print(e.response.json())

    return "OK", 200


@bp.post("/set_limits")
@validate_id
def set_limits(ms_id):
    for pv in request.json.get("pvs"):
        update = 0

        try:
            update = User.objects(ms_id=ms_id, pvs__name=pv.get("name")).update(
                set__pvs__S__hi_limit=pv.get("hi_limit"), set__pvs__S__lo_limit=pv.get("lo_limit")
            )
        except Exception:
            pass

        if not update:
            new_pv = Pv(
                hi_limit=pv.get("hi_limit"), lo_limit=pv.get("lo_limit"), name=pv.get("name")
            )
            User.objects(ms_id=ms_id).update_one(
                add_to_set__pvs=new_pv,
                upsert=True,
            )
    return "OK", 200


@bp.post("/outlets")
@validate_id_with_username
def set_outlets(ms_id, username):
    if "host" not in request.args or "outlets" not in request.json:
        return "Bad Request", 400

    validated_outlets = {}

    for outlet, status in enumerate(request.json.get("outlets")):
        if status not in [0, 1]:
            continue

        validated_outlets[outlet] = str(status) + ":" + username

    if validated_outlets:
        redis_server.hmset(request.args.get("host"), validated_outlets)
    else:
        return "Bad Request", 400

    return "OK", 200


@bp.get("/outlets")
@validate_id
def get_outlets(ms_id):
    if "host" not in request.args:
        return "Bad Request", 400

    validated_outlets = []

    for status in redis_server.hgetall(request.args.get("host") + ":RB").values():
        validated_outlets.append(1 if status.decode() == "1" else 0)

    return jsonify({"outlets": validated_outlets})


@bp.post("/register_telegram")
@validate_id_with_name
def register_telegram(ms_id, name):
    if "id" not in request.json:
        return "Bad Request", 400

    id = request.json.get("id")

    User.objects(ms_id=ms_id).update_one(set__telegram_id=id)
    return "Message Relayed", send_telegram_message(
        current_app.config["TELEGRAM_TOKEN"], hello.safe_substitute(NAME=name), id
    )

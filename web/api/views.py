import json

from api.util import get_ms_id
from flask import jsonify, request, current_app, Blueprint
from api.models import User, Device
from pywebpush import webpush, WebPushException

bp = Blueprint("simar", __name__)


@bp.get("/")
def status():
    return "ok"


@bp.get("/get_subscriptions")
def get_subscriptions():
    try:
        ms_id = get_ms_id(request.headers["Authorization"])
    except KeyError:
        return "No valid token present", 401

    return jsonify([pv.name for pv in User.objects(ms_id=ms_id)[0].subbed_pvs]), 200


@bp.post("/subscribe")
def subscribe():
    try:
        ms_id = get_ms_id(request.headers["Authorization"])
    except KeyError:
        return "No valid token present", 401

    r_json = request.json
    sub = r_json.get("sub")

    if not r_json.get("pvs"):
        return "Bad Request", 400

    device = Device(
        endpoint=sub.get("endpoint"),
        auth=sub.get("keys").get("auth"),
        p256dh=sub.get("keys").get("p256dh"),
    )
    User.objects(ms_id=ms_id).update_one(
        add_to_set__devices=device,
        add_to_set__subbed_pvs=r_json.get("pvs"),
        upsert=True,
    )

    return jsonify(r_json.get("pvs")), 200


@bp.post("/unsubscribe")
def unsubscribe():
    try:
        ms_id = get_ms_id(request.headers["Authorization"])
    except KeyError:
        return "No valid token present", 401

    if not request.json.get("pvs"):
        return "Bad Request", 400

    User.objects(ms_id=ms_id).update_one(pull__subbed_pvs__name=request.json.get("pvs"))

    return jsonify(request.json.get("pvs")), 200


@bp.delete("/unsubscribe_all")
def unsubscribe_all():
    try:
        ms_id = get_ms_id(request.headers["Authorization"])
    except KeyError:
        return "No valid token present", 401

    User.objects(ms_id=ms_id).delete()
    return "OK", 200


@bp.post("/notify")
def notify():
    count = 0
    try:
        ms_id = get_ms_id(request.headers["Authorization"])
    except KeyError:
        return "No valid token present", 401

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
                vapid_private_key=current_app.config.VAPID_PRIVATE_KEY,
                vapid_claims=current_app.config.VAPID_CLAIMS,
            )
            count += 1
        except WebPushException as e:
            print(e.response.json())

    return "OK", 200

import json

from api.util import get_ms_id
from flask import jsonify, request, current_app, Blueprint
from api.models import Pv, User, Device
from pywebpush import webpush, WebPushException

bp = Blueprint("simar", __name__)


@bp.get("/")
def status():
    return "ok"


@bp.get("/get_subscriptions")
def get_subs():
    try:
        ms_id = get_ms_id(request.headers["Authorization"])
    except KeyError:
        return "No valid token present", 401

    return jsonify([pv.name for pv in User.objects(ms_id=ms_id, pvs__subbed=True)[0].pvs]), 200


@bp.get("/get_pvs")
def get_pvs():
    try:
        ms_id = get_ms_id(request.headers["Authorization"])
    except KeyError:
        return "No valid token present", 401

    try:
        return jsonify([pv.to_mongo() for pv in User.objects(ms_id=ms_id)[0].pvs]), 200
    except Exception:
        return "User not found", 404


@bp.post("/subscribe")
def subscribe():
    if request.method == "GET":
        return jsonify({"public_key": current_app.config.VAPID_PUBLIC_KEY})

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
def unsubscribe():
    try:
        ms_id = get_ms_id(request.headers["Authorization"])
    except KeyError:
        return "No valid token present", 401

    if not request.json.get("pvs"):
        return "Bad Request", 400

    for pv in request.json.get("pvs"):
        User.objects(ms_id=ms_id, pvs__name=pv).update(set__pvs__S__subbed=False)

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


@bp.post("/set_limits")
def set_limits():
    try:
        ms_id = get_ms_id(request.headers["Authorization"])
    except KeyError:
        return "No valid token present", 401

    for pv in request.json.get("pvs"):
        update = 0

        try:
            # user = User.objects(ms_id=ms_id)
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

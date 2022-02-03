import json
from redis import Redis
from api.consts import (
    DETAIL_EQUIPMENT,
    IP_TYPES,
    RESTART_SERVICE,
    STOP_SERVICE,
)
from zoneinfo import ZoneInfo
from datetime import datetime

from api.util import (
    send_telegram_message,
    validate_id,
    validate_id_with_name,
    validate_id_with_username,
    get_pwr_supply_table,
)
from flask import jsonify, request, current_app, Blueprint
from api.models import Pv, User, Device
from api.templates import hello
from pywebpush import webpush, WebPushException

redis_server = Redis(host="redis-db", port=6379, decode_responses=True)
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

    if not r_json.get("pvs") or not sub:
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
    if not any(s in request.json for s in ["host", "outlets"]):
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
def get_outlets():
    if "host" not in request.args:
        return "Bad Request", 400

    validated_outlets = []

    for status in redis_server.hgetall(request.args.get("host") + ":RB").values():
        validated_outlets.append(1 if status == "1" else 0)

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


@bp.get("/status")
def get_node_status():
    if "host" not in request.args:
        return "Bad Request", 400

    status = redis_server.hget(request.args["host"], "state_string")

    if status:
        return jsonify({"status": status})
    else:
        cursor = 0
        hostname = "BBB:*:" + request.args["host"][request.args["host"].find(":") + 1 :]
        name = ""
        searched = False
        while not name and (cursor != 0 or not searched):
            cursor, name = redis_server.scan(cursor=cursor, match=hostname)
            searched = True

        if name:
            return jsonify({"status": redis_server.hget(name[0], "state_string")})
        else:
            return "Node not found", 404


@bp.get("/beaglebones")
def get_beaglebones():
    valid_bbbs = []
    ps = {}
    if "ps" in request.args:
        ps = get_pwr_supply_table()

    for bbb in redis_server.scan_iter("BBB*"):
        if any(s in bbb for s in [":Command", ":Logs"]):
            continue

        bbb_info = redis_server.hgetall(bbb)

        if "matching_bbb" in bbb_info and bbb_info["matching_bbb"]:
            bbb_info["role"] = bbb_info["matching_bbb"].capitalize()
        else:
            bbb_info["role"] = "Primary"

        if "sector" in bbb_info:
            if bbb_info["sector"] == "Outros":
                bbb_info["sector"] = "Others"
            else:
                bbb_info["sector"] = bbb_info["sector"].replace("Sala", "IA-")
        else:
            bbb_info["sector"] = "Others"

        try:
            bbb_info["ip_type"] = IP_TYPES[bbb_info["ip_type"]]
        except KeyError:
            bbb_info["ip_type"] = "Static"

        try:
            bbb_info["equipment"] = DETAIL_EQUIPMENT[bbb_info["details"].split(" ")[0]]
        except KeyError:
            bbb_info["equipment"] = "Unknown"

        if bbb_info["state_string"][0:3] == "BBB":
            bbb_info["state_string"] = f"Moved - {bbb_info['state_string']}"

        if "ip_address" not in bbb_info:
            bbb_info["ip_address"] = bbb.split(":")[1]

        bbb_info["last_seen"] = (
            datetime.fromtimestamp(float(bbb_info["ping_time"]), ZoneInfo("America/Sao_Paulo"))
            .isoformat()
            .replace("T", " ")
        )

        bbb_info["key"] = bbb
        if "nameservers" in bbb_info:
            bbb_info["nameservers"] = bbb_info["nameservers"].split(",")

        if "ps" in request.args:
            try:
                bbb_info["name"] = bbb_info["name"].replace("--", ":")
                bbb_info = bbb_info | ps[bbb_info["ip_address"]]
                valid_bbbs.append(bbb_info)
            except KeyError:
                pass
        else:
            valid_bbbs.append(bbb_info)

    return jsonify(valid_bbbs)


@bp.post("/services")
@validate_id
def change_services(ms_id):
    if not any(s in request.json for s in ["restart", "stop"]):
        return (
            "Bad Request",
            400,
        )

    for action, code in [("restart", RESTART_SERVICE), ("stop", STOP_SERVICE)]:
        for target in request.json.get(action) or []:
            for service in target.get("services"):
                redis_server.rpush(f"{target.get('key')}:Command", f"{code};{service}")

    return "OK", 200


@bp.post("/beaglebones")
@validate_id
def change_beaglebones(ms_id):
    if not any(s in request.json for s in ["delete", "reboot"]):
        return "Bad Request", 400

    for target in request.json.get("delete") or []:
        redis_server.delete(target, target + ":Command", target + ":Logs")

    for target in request.json.get("reboot") or []:
        redis_server.rpush(f"{target}:Command", 1)

    return "OK", 200


@bp.get("/logs")
def get_logs():
    logs = []
    for bbb in redis_server.scan_iter("BBB*Logs"):
        raw_logs = redis_server.hgetall(bbb)
        for timestamp, message in raw_logs.items():
            logs.append(
                {
                    "ip_address": bbb.split(":")[1],
                    "name": bbb.split(":")[2],
                    "timestamp": timestamp,
                    "message": message,
                    "date": datetime.fromtimestamp(float(timestamp)).isoformat().replace("T", " "),
                    "key": ":".join(bbb.split(":")[:-1]),
                }
            )

    return jsonify(logs)


# Blame DELETE not accepting bodies
@bp.post("/del_logs")
@validate_id
def delete_logs(ms_id):
    if not request.json:
        return "Bad Request", 400

    for bbb in request.json:
        redis_server.hdel(f"{bbb.get('key')}:Logs", *bbb.get("timestamps"))

    return "OK", 200

from redis import Redis
from api.consts import (
    DETAIL_EQUIPMENT,
    IP_TYPES,
    RESTART_SERVICE,
    SET_HOSTNAME,
    SET_IP,
    SET_NAMESERVERS,
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
from flask import jsonify, current_app, Blueprint
from api.models import (
    LogSchema,
    NetworkingSchema,
    OutletSchema,
    Pv,
    PvSchema,
    ServiceSchema,
    SubscriptionSchema,
    User,
    Device,
    Ac,
    Outlet,
)
from api.templates import hello
from bson import ObjectId
from webargs import fields
from webargs.flaskparser import use_args

redis_server = Redis(host="redis-db", port=6379, decode_responses=True)
bp = Blueprint("simar", __name__)


@bp.get("/pvs")
@validate_id
def get_pvs(ms_id):
    try:
        return jsonify([pv.to_mongo() for pv in User.objects(ms_id=ms_id)[0].pvs]), 200
    except Exception:
        return "User not found", 404


@bp.post("/subscribe")
@use_args(SubscriptionSchema())
@validate_id
def subscribe(ms_id, args):
    device = Device(
        endpoint=args["endpoint"],
        auth=args["auth"],
        p256dh=args["p256dh"],
        user_agent=args["user_agent"],
        host=args["host"],
    )

    User.objects(ms_id=ms_id).update_one(
        add_to_set__devices=device,
    )

    if not args.get("pvs"):
        return "OK", 200

    for pv in args.get("pvs"):
        update = User.objects(ms_id=ms_id, pvs__name=pv["name"]).update_one(
            set__pvs__S__subbed=True,
        )

        if not update:
            new_pv = Pv(
                name=pv(pv["name"]),
                hi_limit=pv["hi_limit"],
                lo_limit=pv["lo_limit"],
                subbed=True,
            )

            User.objects(ms_id=ms_id).update_one(
                add_to_set__pvs=new_pv,
                add_to_set__devices=device,
                upsert=True,
            )

    return jsonify(args["pvs"]), 200


@bp.post("/unsubscribe")
@use_args({"pvs": fields.List(fields.Str, required=True)})
@validate_id
def unsubscribe(ms_id, args):
    for pv in args["pvs"]:
        User.objects(ms_id=ms_id, pvs__name=pv).update(set__pvs__S__subbed=False)

    return jsonify(args["pvs"]), 200


@bp.delete("/limits")
@validate_id
def unsubscribe_all(ms_id):
    User.objects(ms_id=ms_id).delete()
    return "OK", 200


@bp.post("/limits")
@use_args(PvSchema(many=True))
@validate_id
def set_limits(ms_id, args):
    for pv in args:
        update = 0

        try:
            update = User.objects(ms_id=ms_id, pvs__name=pv["name"]).update(
                set__pvs__S__hi_limit=pv["hi_limit"], set__pvs__S__lo_limit=pv["lo_limit"]
            )
        except Exception:
            pass

        if not update:
            new_pv = Pv(hi_limit=pv["hi_limit"], lo_limit=pv["lo_limit"], name=pv["name"])
            User.objects(ms_id=ms_id).update_one(
                add_to_set__pvs=new_pv,
                upsert=True,
            )
    return "OK", 200


@bp.post("/outlets/<string:host>")
@use_args(OutletSchema(many=True))
@validate_id_with_username
def set_outlets(ms_id, username, args, host):
    validated_outlets = {}
    try:
        outlet_names = {}
        for outlet in args:
            if not isinstance(outlet["setpoint"], bool):
                return "Bad Request", 400

            validated_outlets[outlet["id"]] = "1" if outlet["setpoint"] else "0" + ":" + username
            outlet_names[f"set__ac_power__S__outlets__{outlet['id']}__name"] = outlet.get(
                "name"
            ) or str(outlet["id"])

        user = User.objects(ms_id=ms_id)
        if not user.filter(ac_power__host=host).update(**outlet_names):
            user.update(
                add_to_set__ac_power=Ac(
                    host=host, outlets=[Outlet(name=n) for n in list(outlet_names.values())]
                ),
                upsert=True,
            )

        redis_server.hmset(host, validated_outlets)
    except AttributeError:
        return "Bad Request", 400

    return "OK", 200


@bp.get("/outlets/<string:host>")
@validate_id
def get_outlets(ms_id, host):
    validated_outlets = []

    try:
        names = [
            o.name
            for o in User.objects(ms_id=ms_id, ac_power__host=host)
            .fields(ac_power__outlets=1)
            .first()
            .ac_power[0]
            .outlets
        ]
    except AttributeError:
        names = [str(i) for i in range(0, 7)]

    try:
        for i, status in enumerate(redis_server.hgetall(host + ":RB").values()):
            validated_outlets.append({"status": 1 if status == "1" else 0, "name": names[i]})
    except (KeyError, AttributeError):
        pass

    return jsonify(validated_outlets)


@bp.post("/telegram/<string:id>")
@validate_id_with_name
def register_telegram(ms_id, name, id):
    User.objects(ms_id=ms_id).update_one(set__telegram_id=id)
    return "Message Relayed", send_telegram_message(
        current_app.config["TELEGRAM_TOKEN"], hello.safe_substitute(NAME=name), id
    )


@bp.delete("/telegram/<string:id>")
@validate_id
def delete_telegram(ms_id, id):
    User.objects(ms_id=ms_id).update(pull__devices__telegram_id=id)
    return "OK", 200


@bp.get("/status/<string:host>")
def get_node_status(host):
    status = redis_server.hget(host, "state_string")

    if status:
        return jsonify({"status": status})
    else:
        cursor = 0
        hostname = "BBB:*:" + host[host.find(":") + 1 :]
        name = ""
        searched = False
        while not name and (cursor != 0 or not searched):
            cursor, name = redis_server.scan(cursor=cursor, match=hostname)
            searched = True

        if name:
            return jsonify({"status": redis_server.hget(name[0], "state_string")})
        else:
            return "Node not found", 404


@bp.get("/devices")
@validate_id
def get_devices(ms_id):
    try:
        user = User.objects(ms_id=ms_id).first().to_mongo()
        return jsonify({"devices": user["devices"], "telegram_id": user.get("telegram_id")})
    except (KeyError, IndexError):
        return "No devices found for user", 404


@bp.delete("/devices")
@use_args({"endpoints": fields.List(fields.Str)}, location="query")
@validate_id
def delete_devices(ms_id, args):
    User.objects(ms_id=ms_id).update(pull__devices__endpoint__in=args["endpoints"])
    return "OK", 200


@bp.get("/beaglebones")
@use_args({"ps": fields.Bool(required=False)}, location="query")
def get_beaglebones(args):
    valid_bbbs = []
    ps = {}
    if args.get("ps"):
        ps = get_pwr_supply_table()

    for bbb in redis_server.scan_iter("BBB*"):
        if any(s in bbb for s in [":Command", ":Logs"]):
            continue

        keys = [
            "matching_bbb",
            "sector",
            "ip_type",
            "name",
            "equipment",
            "state_string",
            "ip_address",
            "ping_time",
        ]
        bbb_info = {keys[i]: v for i, v in enumerate(redis_server.hmget(bbb, keys))}

        if "matching_bbb" in bbb_info and bbb_info["matching_bbb"]:
            bbb_info["role"] = bbb_info["matching_bbb"].capitalize()
        else:
            bbb_info["role"] = "Primary"

        if "sector" not in bbb_info or bbb_info["sector"] == "Outros":
            bbb_info["sector"] = "Others"
        elif bbb_info["sector"] == "Conectividade":
            bbb_info["sector"] = "Conectivity"
        else:
            bbb_info["sector"] = bbb_info["sector"].replace("Sala", "IA-")

        if "name" not in bbb_info:
            bbb_info["name"] = "Unknown"

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

        try:
            bbb_info["last_seen"] = datetime.fromtimestamp(
                float(bbb_info["ping_time"]), ZoneInfo("America/Sao_Paulo")
            ).strftime("%Y-%m-%d %X")
        except KeyError:
            bbb_info["last_seen"] = datetime.now(tz=ZoneInfo("America/Sao_Paulo")).strftime(
                "%Y-%m-%d %X"
            )

        del bbb_info["matching_bbb"]
        del bbb_info["ping_time"]
        bbb_info["key"] = bbb

        if ps:
            try:
                bbb_info["name"] = bbb_info["name"].replace("--", ":")
                bbb_info = bbb_info | ps[bbb_info["ip_address"]]
                valid_bbbs.append(bbb_info)
            except KeyError:
                pass
        else:
            valid_bbbs.append(bbb_info)

    return jsonify(valid_bbbs)


@bp.get("/beaglebones/details/<string:node>")
def get_beaglebone_details(node):
    keys = ["nameservers", "details", "disk_usage"]
    return {keys[i]: v for i, v in enumerate(redis_server.hmget(node, keys))}


@bp.post("/beaglebones/networking")
@use_args(NetworkingSchema(many=True))
@validate_id
def configure_networking(ms_id, args):
    for node in args:
        if node.get("ip"):
            redis_server.rpush(
                f"{node['key']}:Command",
                f"{SET_IP};{node['type']};{node['ip']};{node['mask']};{node['gateway']}",
            )

        if node.get("hostname"):
            redis_server.rpush(f"{node['key']}:Command", f"{SET_HOSTNAME};{node['hostname']}")

        if node.get("nameservers"):
            redis_server.rpush(
                f"{node['key']}:Command", f"{SET_NAMESERVERS};{';'.join(node['nameservers'])}"
            )

        return "OK", 200


@bp.post("/beaglebones/services")
@use_args(ServiceSchema(many=True))
@validate_id
def change_services(ms_id, args):
    for target in args:
        for action, code in [("restart", RESTART_SERVICE), ("stop", STOP_SERVICE)]:
            for service in target.get(action) or []:
                redis_server.rpush(f"{target['key']}:Command", f"{code};{service}")

    return "OK", 200


@bp.post("/beaglebones")
@use_args(
    {
        "delete": fields.List(fields.Str(), missing=[]),
        "reboot": fields.List(fields.Str(), missing=[]),
    }
)
@validate_id
def change_beaglebones(ms_id, args):
    for target in args["delete"]:
        redis_server.delete(target, target + ":Command", target + ":Logs")

    for target in args["reboot"]:
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
                    "date": datetime.fromtimestamp(
                        float(timestamp), ZoneInfo("America/Sao_Paulo")
                    ).strftime("%Y-%m-%d %X"),
                    "key": ":".join(bbb.split(":")[:-1]),
                }
            )

    return jsonify(logs)


# Blame DELETE not accepting bodies
@bp.post("/del_logs")
@use_args(LogSchema(many=True))
@validate_id
def delete_logs(ms_id, args):
    for bbb in args:
        redis_server.hdel(f"{bbb['key']}:Logs", *bbb["timestamps"])

    return "OK", 200


@bp.get("/notification")
@validate_id
def get_notifications(ms_id):
    try:
        return jsonify(
            [
                {"date": n.date, "message": n.message, "oid": str(n.oid)}
                for n in User.objects(ms_id=ms_id)[0].notifications
            ]
        )
    except IndexError:
        return "No user found", 404


@bp.delete("/notification")
@use_args({"oid": fields.List(fields.Str)}, location="query")
@validate_id
def delete_notifications(ms_id, args):
    User.objects(ms_id=ms_id).update(
        pull__notifications__oid__in=[ObjectId(o) for o in args["oid"]]
    )
    return "OK", 200


@bp.errorhandler(422)
@bp.errorhandler(400)
def handle_error(err):
    headers = err.data.get("headers", None)
    messages = err.data.get("messages", ["Invalid request."])
    if headers:
        return jsonify({"errors": messages}), err.code, headers
    else:
        return jsonify({"errors": messages}), err.code

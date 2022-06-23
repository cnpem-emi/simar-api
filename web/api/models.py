from mongoengine import (
    Document,
    EmbeddedDocumentField,
    StringField,
    ListField,
    EmbeddedDocument,
)
from mongoengine.fields import (
    BooleanField,
    FloatField,
    IntField,
    DateTimeField,
    SortedListField,
    ObjectIdField,
)
from bson.objectid import ObjectId

from datetime import datetime
from marshmallow import Schema, ValidationError, fields, validates_schema


class Pv(EmbeddedDocument):
    name = StringField(required=True)
    hi_limit = FloatField(required=True)
    lo_limit = FloatField(required=True)
    subbed = BooleanField(required=True, default=False)


class Device(EmbeddedDocument):
    endpoint = StringField(required=True)
    user_agent = StringField(required=True)
    host = StringField(required=True)
    auth = StringField(required=True)
    p256dh = StringField(required=True)


class Notification(EmbeddedDocument):
    date = DateTimeField(default=datetime.now())
    message = StringField(required=True)
    oid = ObjectIdField(required=True, default=ObjectId)


class Outlet(EmbeddedDocument):
    name = StringField(required=True)


class Ac(EmbeddedDocument):
    host = StringField(required=True)
    outlets = ListField(EmbeddedDocumentField(Outlet), required=False)


class User(Document):
    ms_id = StringField(required=True, unique=True)
    devices = ListField(EmbeddedDocumentField(Device), required=False)
    notifications = SortedListField(
        EmbeddedDocumentField(Notification), required=False, ordering="date"
    )
    pvs = ListField(EmbeddedDocumentField(Pv), required=True)
    telegram_id = IntField(required=False)
    ac_power = ListField(EmbeddedDocumentField(Ac), required=False)

    meta = {
        "indexes": [
            {"fields": ["-notifications"], "unique": False, "sparse": False},
        ],
    }


class NetworkingSchema(Schema):
    key = fields.Str(required=True)
    nameservers = fields.List(fields.Str, required=False)
    hostname = fields.Str(required=False)
    ip = fields.Str(required=False)
    mask = fields.Str(required=False)
    gateway = fields.Str(required=False)
    type = fields.Str(required=False)

    @validates_schema
    def validate_requires(self, data, **kwargs):
        if "ip" in data and any(v not in data for v in ["mask", "gateway", "type"]):
            raise ValidationError("'type', 'gateway' and 'mask' are required when 'ip' is set")


class PvSchema(Schema):
    name = fields.Str(required=True)
    hi_limit = fields.Float(required=True)
    lo_limit = fields.Float(required=True)
    subbed = fields.Bool(required=False, load_default=False)

    @validates_schema
    def validate_limits(self, data, **kwargs):
        if data["hi_limit"] < data["lo_limit"]:
            raise ValidationError("The lower limit should not be greater than the higher limit")


class SubscriptionSchema(Schema):
    endpoint = fields.Str(required=True)
    auth = fields.Str(required=True)
    p256dh = fields.Str(required=True)
    user_agent = fields.Str(required=False, load_default="Unknown")
    host = fields.Str(required=True)
    pvs = fields.List(fields.Nested(PvSchema, required=False))


class ServiceSchema(Schema):
    key = fields.Str(required=True)
    restart = fields.List(fields.Str, required=False, load_default=[])
    stop = fields.List(fields.Str, required=False, load_default=[])


class LogSchema(Schema):
    key = fields.Str(required=True)
    timestamps = fields.List(fields.Str, required=True)


class OutletSchema(Schema):
    id = fields.Int(required=True)
    setpoint = fields.Bool(required=True)
    name = fields.String(required=False)

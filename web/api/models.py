from mongoengine import (
    Document,
    EmbeddedDocumentField,
    StringField,
    ListField,
    EmbeddedDocument,
)
from mongoengine.fields import BooleanField, FloatField, IntField


class Pv(EmbeddedDocument):
    name = StringField(required=True)
    hi_limit = FloatField(required=True)
    lo_limit = FloatField(required=True)
    subbed = BooleanField(required=True, default=False)


class Device(EmbeddedDocument):
    endpoint = StringField(required=True)
    auth = StringField(required=True)
    p256dh = StringField(required=True)


class User(Document):
    ms_id = StringField(required=True, unique=True)
    devices = ListField(EmbeddedDocumentField(Device), required=False)
    pvs = ListField(EmbeddedDocumentField(Pv), required=True)
    telegram_id = IntField(required=False)

from mongoengine import (
    Document,
    EmbeddedDocumentField,
    StringField,
    ListField,
    EmbeddedDocument,
)
from mongoengine.fields import FloatField


class Pv(EmbeddedDocument):
    name = StringField(required=True)
    hi_limit = FloatField(required=True)
    lo_limit = FloatField(required=True)


class Device(EmbeddedDocument):
    endpoint = StringField(required=True, unique=True)
    auth = StringField(required=True)
    p256dh = StringField(required=True)


class User(Document):
    ms_id = StringField(required=True, unique=True)
    devices = ListField(EmbeddedDocumentField(Device), required=True)
    subbed_pvs = ListField(EmbeddedDocumentField(Pv), required=True)

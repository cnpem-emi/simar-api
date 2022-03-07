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
    oid = ObjectIdField(required=True, default=ObjectId, unique=True, primary_key=True)

    def to_json(self):
        return {"date": self.date, "message": self.message, "oid": str(self.oid)}


class User(Document):
    ms_id = StringField(required=True, unique=True)
    devices = ListField(EmbeddedDocumentField(Device), required=False)
    notifications = SortedListField(
        EmbeddedDocumentField(Notification), required=False, ordering="date"
    )
    pvs = ListField(EmbeddedDocumentField(Pv), required=True)
    telegram_id = IntField(required=False)

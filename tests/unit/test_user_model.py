import unittest
from web.api.models import User, Pv
from mongoengine import connect, disconnect, errors
import pytest

pv = Pv(name="Me", hi_limit="100", lo_limit="0", subbed="False")


class TestUser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        connect("mongoenginetest", host="mongomock://localhost")

    @classmethod
    def tearDownClass(cls):
        disconnect()

    def test_new_user(self):
        user = User(ms_id="msid", pvs=[pv])
        user.save()

        assert User.objects().first().ms_id == "msid"

    def test_user_unique(self):
        user = User(ms_id="other_msid", pvs=[pv])
        user.save()
        with pytest.raises(errors.NotUniqueError):
            user_2 = User(ms_id="other_msid", pvs=[pv])
            user_2.save()

    def test_user_different(self):
        user = User(ms_id="new_msid", pvs=[pv])
        user.save()

        user_2 = User(ms_id="newer_msid", pvs=[pv])
        user_2.save()

        assert User.objects().order_by("-id").first().ms_id == "newer_msid"

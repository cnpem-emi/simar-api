from flask import Flask
from mongoengine import connect
from config import Config
from api.monitor import main_loop
from threading import Thread
from flask_cors import CORS

from api.views import bp

application = Flask(__name__)
CORS(application)
application.config.from_object(Config)

connect(
    "simar",
    host=application.config["MONGO_HOST"],
    port=application.config["MONGO_PORT"],
    username=application.config["MONGO_USER"],
    password=application.config["MONGO_PASS"],
    authentication_source=application.config["MONGO_AUTH_DB"],
)

monitor_thread = Thread(
    target=lambda: main_loop(
        application.config["VAPID_PRIVATE_KEY"],
        application.config["VAPID_CLAIMS"],
        application.config["TELEGRAM_TOKEN"],
    )
)
monitor_thread.start()

application.register_blueprint(bp, url_prefix="/simar/api")

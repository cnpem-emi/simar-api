import os


class Config(object):
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    DEBUG = False
    TESTING = False
    ENV = "production"

    THREADS_PER_PAGE = 2

    with open("/run/secrets/VAPID_PRIVATE_KEY") as secret:
        VAPID_PRIVATE_KEY = secret.read()

    with open("/run/secrets/TELEGRAM_BOT_TOKEN") as secret:
        TELEGRAM_TOKEN = secret.read().split("\n")[0]

    VAPID_PUBLIC = os.getenv("VAPID_PUBLIC")
    VAPID_CLAIMS = {"sub": "mailto:guilherme.freitas@cnpem.br"}

    MONGO_HOST = os.getenv("MONGO_HOST")
    MONGO_PORT = int(os.getenv("MONGO_PORT"))
    MONGO_USER = os.getenv("MONGO_USER")
    MONGO_PASS = os.getenv("MONGO_PASS")
    MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB")

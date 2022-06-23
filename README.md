# SIMAR - API
[![Lint](https://github.com/cnpem-iot/simar-api/actions/workflows/python-linting.yml/badge.svg)](https://github.com/cnpem-iot/simar-api/actions/workflows/python-linting.yml)

SIMAR's REST API for notifications and more. Utilizes the Web Push API to push notifications to browsers.

For detailed information on endpoints and other documentation, check the [OpenAPI docs](https://cnpem-sei.github.io/simar-api/).

## Running (Docker)

```bash
docker-compose build
docker-compose up
```

## Running 

```bash
pip3 install -r requirements.txt
cd web
gunicorn --bind 0.0.0.0:5000 app:application 
```

## Limitations
Due to anti-spam restrictions, please do not perform a large number of notifications every minute. That may cause the web push API endpoint to get deactivated, forcing the user to re-register a new subscription.


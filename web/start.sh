#!/bin/bash
set -m 

gunicorn --bind 0.0.0.0:5000 app:application -D
nginx -g 'daemon off;'
#!/bin/bash
set -m 

gunicorn --bind 127.0.0.1:5000 app:application -D
nginx -g 'daemon off;'

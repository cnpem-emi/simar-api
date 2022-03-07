FROM python:3.10.0-slim-bullseye

ENV APP_HOME=/home/app
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

COPY web/ $APP_HOME

RUN ln -sf /usr/share/zoneinfo/Brazil/East /etc/localtime && apt-get update && apt-get install -y --no-install-recommends netcat nginx
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY nginx/nginx.conf /etc/nginx/nginx.conf

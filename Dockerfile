FROM python:3-alpine

WORKDIR /bot
RUN chmod 777 /bot

# install ca-certificates so that HTTPS works consistently
RUN apk add --no-cache --update \
      ca-certificates \
      aria2 \
      libmagic \
      py3-lxml \
      curl \
      pv \
      jq

RUN apk add --no-cache --update --virtual .build-deps \
      build-base \
      libffi-dev \
      openssl-dev

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
RUN apk del .build-deps
COPY . .
RUN chmod +x *.sh

CMD ["sh", "./start.sh"]

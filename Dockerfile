FROM python:3.8-slim-buster

WORKDIR /usr/src/app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update
RUN apt-get install -y aria2


CMD ["bash","start.sh"]
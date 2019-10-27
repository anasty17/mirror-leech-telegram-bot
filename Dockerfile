FROM python:3.8-slim-buster

RUN mkdir /bot
RUN chmod 777 /bot
COPY . /bot
WORKDIR /bot

RUN apt-get update
RUN apt-get install -y aria2
RUN pip install -r /bot/requirements.txt


CMD ["bash","start.sh"]
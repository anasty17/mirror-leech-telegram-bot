FROM ubuntu:18.04

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app
COPY . .
RUN apt-get update
RUN apt-get install -y aria2 megatools ffmpeg python3 python3-pip
RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["bash","start.sh"]

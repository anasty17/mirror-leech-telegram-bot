FROM ubuntu:20.04

WORKDIR /app
RUN mkdir ./app
RUN chmod 777 ./app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "start.sh"]

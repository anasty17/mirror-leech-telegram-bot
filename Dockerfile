FROM anasty17/mltb:latest
# FROM anasty17/mltb-oracle:latest

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m mltb
USER mltb

CMD ["bash", "start.sh"]

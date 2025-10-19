FROM anasty17/mltb:dev

WORKDIR /mltb
RUN chmod 777 /mltb

RUN python3 -m venv mltbenv

COPY requirements.txt .
RUN mltbenv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "start.sh"]

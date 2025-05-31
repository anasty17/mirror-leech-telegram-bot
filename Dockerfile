FROM anasty17/mltb:latest

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

RUN python3 -m venv mltbenv

COPY requirements.txt .
RUN mltbenv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

# Create a non-root user for Heroku
RUN addgroup -S heroku_group && adduser -S -G heroku_group heroku_user
USER heroku_user

CMD ["bash", "start.sh"]

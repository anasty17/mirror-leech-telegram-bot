FROM anasty17/mltb:latest

WORKDIR /app
RUN chmod 755 /app

RUN python3 -m venv mltbenv

COPY requirements.txt .
RUN mltbenv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i 's/\r$//' *.sh && \
    find . -type f \( -name '*.py' -o -name '*.sh' -o -name '*.yml' -o -name '*.yaml' \) -exec chmod 644 {} + && \
    chmod 755 *.sh

CMD ["bash", "start.sh"]

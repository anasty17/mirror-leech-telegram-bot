FROM notml/notdoc:latest
# FROM notml/notdoc-oracle:latest

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

COPY extract pextract /usr/local/bin/
RUN chmod +x /usr/local/bin/extract && chmod +x /usr/local/bin/pextract && chmod +x aria.sh && chmod 600 .netrc

CMD ["bash", "start.sh"]

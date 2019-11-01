FROM ubuntu:18.04

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

RUN apt-get -qq update
RUN apt-get -qq install -y python3 python3-pip rar unzip git aria2 g++ gcc autoconf automake \
    m4 libtool qt4-qmake make libqt4-dev libcurl4-openssl-dev \
    libcrypto++-dev libsqlite3-dev libc-ares-dev \
    libsodium-dev libnautilus-extension-dev \
    libssl-dev libfreeimage-dev swig curl pv jq ffmpeg locales python3-lxml

# Installing mega sdk python binding
ENV MEGA_SDK_VERSION '3.6.4'
RUN git clone https://github.com/meganz/sdk.git sdk
WORKDIR sdk
RUN git checkout v$MEGA_SDK_VERSION && ./autogen.sh && \
    ./configure --disable-silent-rules --enable-python --disable-examples && \
    make -j$(nproc --all) && cd bindings/python/ && \
    python setup.py bdist_wheel && cd dist/ && \
    pip install --no-cache-dir megasdk-$MEGA_SDK_VERSION-*.whl


COPY requirements.txt .
COPY extract /usr/local/bin
RUN chmod +x /usr/local/bin/extract
RUN pip3 install --no-cache-dir -r requirements.txt
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
COPY . .
COPY netrc /root/.netrc
RUN chmod +x aria.sh

CMD ["bash","start.sh"]



FROM python:3.11-slim
WORKDIR /boss-tracker

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*
COPY . ./app
#COPY ./run_bot.py ./run_bot.py
#COPY ./run_websocket.py ./run_websocket.py
COPY ./requirements.txt ./requirements.txt

RUN apt-get update
RUN /bin/bash -c "pip install -r requirements.txt"

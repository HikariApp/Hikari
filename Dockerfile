FROM python:3.12.6-bookworm

RUN mkdir app
WORKDIR /app
VOLUME [ "/opt" ]

# For Google Cloud Run
EXPOSE 9000

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

RUN apt-get update && apt-get install -y ffmpeg

CMD [ "python3", "startup.py"]

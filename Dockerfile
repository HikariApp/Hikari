FROM python:3.14-bookworm

# Install uv and uvx from Astral's GitHub Container Registry
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Same as before
RUN mkdir app
WORKDIR /app
VOLUME [ "/opt" ]

COPY requirements.txt requirements.txt
RUN uv venv && uv pip sync requirements.txt

COPY . .

# We don't need to install ffmpeg manually anymore since this will be handled by lavalink server right now
RUN apt-get update

CMD [ "uv", "run", "startup.py"]

# ---- Builder stage ----
FROM python:3.13-slim-bookworm AS builder

# Bring in uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# git is needed at build time because discord-ext-voice-recv installs
# from a git source. Lives only in the builder — not in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# uv build-time settings:
#   - compile bytecode for faster cold starts
#   - copy (not symlink) so the venv is self-contained for the next stage
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install deps first, using ONLY the lockfiles, so this layer caches
# and doesn't bust every time your source code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now bring in the source and install the project itself
COPY . .
RUN uv sync --frozen --no-dev


# ---- Runtime stage ----
FROM python:3.13-slim-bookworm

WORKDIR /app
VOLUME [ "/opt" ]

# Copy the fully-built venv and app from the builder
COPY --from=builder /app /app

# Install runtime dependencies for audio processing.
# These are needed for the bot to handle audio streams.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libopus0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Put the venv on PATH so we can call the interpreter directly
ENV PATH="/app/.venv/bin:$PATH"

CMD [ "python", "startup.py" ]

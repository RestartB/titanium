FROM ghcr.io/astral-sh/uv:python3.13-trixie

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSf https://atlasgo.sh | sh

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY . .

RUN mkdir -p migrations

ENV ENVIRONMENT=docker

CMD ["uv", "run", "main.py"]
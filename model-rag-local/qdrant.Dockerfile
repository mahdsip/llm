FROM qdrant/qdrant:latest

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl wget \
 && rm -rf /var/lib/apt/lists/*

FROM debian:bookworm-slim@sha256:e67eeead736ff7bbe258ef088bff683635c561b1fcfefad0806c1df4ab49ce0e AS cpp
COPY debian.sources /etc/apt/sources.list.d/debian.sources
COPY apt-network.conf /etc/apt/apt.conf.d/99course-network
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libboost-all-dev libtbb-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --chmod=0755 aider-cpp-test.sh /aider/benchmark/cpp-test.sh
WORKDIR /exercise

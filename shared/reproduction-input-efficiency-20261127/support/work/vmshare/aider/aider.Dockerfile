FROM python:3.11.13-slim-bookworm AS python
COPY python-test-packages/ /usr/local/lib/python3.11/site-packages/
RUN python -m pytest --version
WORKDIR /exercise

FROM golang:1.21.5-bookworm AS go
WORKDIR /exercise

FROM rust:1.85.1-bookworm AS rust
WORKDIR /exercise

FROM debian:bookworm-slim AS cpp
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libboost-all-dev libtbb-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --chmod=0755 aider-cpp-test.sh /aider/benchmark/cpp-test.sh
WORKDIR /exercise

FROM node:20-bookworm-slim AS javascript
WORKDIR /npm-install
RUN npm init -y && npm install --no-audit --no-fund jest@29.7.0 @babel/core@7.25.2 \
    @exercism/babel-preset-javascript@0.2.1 @exercism/eslint-config-javascript@0.6.0 \
    @types/jest@29.5.12 @types/node@20.12.12 babel-jest@29.6.4 core-js@3.37.1 eslint@8.49.0
COPY --chmod=0755 aider-npm-test.sh /aider/benchmark/npm-test.sh
WORKDIR /exercise

FROM gradle:8.7-jdk21 AS java
WORKDIR /exercise
COPY phone-number-build.gradle /exercise/build.gradle
COPY JavaEnvironmentCheck.java /exercise/src/test/java/JavaEnvironmentCheck.java
RUN gradle --no-daemon test && rm -rf /exercise/build /exercise/src /exercise/.gradle /exercise/build.gradle

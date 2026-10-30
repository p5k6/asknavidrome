FROM alpine:3.22.7 AS build
LABEL maintainer="Ross Stewart <rosskouk@gmail.com>"
LABEL org.opencontainers.image.source=https://github.com/rosskouk/asknavidrome

RUN apk add --no-cache python3 py3-pip build-base python3-dev libffi-dev openssl-dev

WORKDIR /opt

# The venv is created without pip so that no installer ships in the final image
RUN python3 -m venv --without-pip env

COPY skill/requirements-docker.txt /src/requirements-docker.txt

RUN pip --no-cache-dir --python /opt/env/bin/python install -r /src/requirements-docker.txt


FROM alpine:3.22.7
LABEL maintainer="Ross Stewart <rosskouk@gmail.com>"
LABEL org.opencontainers.image.source=https://github.com/rosskouk/asknavidrome

# Pick up security fixes released since the base image was published
RUN apk upgrade --no-cache && \
    apk add --no-cache python3 && \
    adduser -D -H -u 10001 navi

COPY --from=build /opt/env /opt/env
COPY skill /opt/asknavidrome/

WORKDIR /opt/asknavidrome

# Activate Python Virtual Environment
ENV PATH="/opt/env/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER navi

EXPOSE 5000

ENTRYPOINT ["python3", "app.py"]

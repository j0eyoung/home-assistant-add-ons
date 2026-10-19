# Wraps https://github.com/gnzsnz/ib-gateway-docker so its settings come from the add-on's
# Configuration tab (/data/options.json) instead of docker environment variables.
# Base image fixed here on purpose: Home Assistant passes its own Alpine base as BUILD_FROM,
# so that argument is deliberately not used.
FROM ghcr.io/gnzsnz/ib-gateway:stable

USER root
RUN apt-get update && apt-get install -y --no-install-recommends jq && rm -rf /var/lib/apt/lists/*
COPY addon_run.sh /addon_run.sh
RUN chmod 755 /addon_run.sh

# Starts as root only to read /data/options.json, then drops to the image's normal user.
CMD ["/addon_run.sh"]

# =============================================================================
# HYDRA-UMC-DETECTION-HEF - Container Build: Dockerfile
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
# Real, minimal image for the model-registry HTTP API (api.py's own
# RegistryServer, stdlib http.server - pyproject.toml's own dependencies
# is deliberately []). Same --addr/--port/--registry/--models-dir CLI the
# real CM5 systemd unit (systemd/hydra-umc-detection-hef.service) already
# runs, just bound to 0.0.0.0 instead of 127.0.0.1 here - a container's
# own network namespace already isolates it the way the systemd unit's
# loopback bind does on bare metal, and 127.0.0.1 inside a container
# would be unreachable from HYDRA-UMC-VISION-NODE's own container over
# the compose network. Non-root, matching that same unit's own
# User=hydra-umc-detection-hef. Consumed by HYDRA-UMC-VISION-NODE's own
# docker-compose.yml as the "detection-hef" service.

FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --system --create-home --home-dir /home/hydra hydra
# A real, valid, empty registry - the same safely-servable starting state
# systemd/hydra-umc-detection-hef.service's own header comment documents
# (GET /registry returns zero entries, not a startup crash) - a real
# populated registry.json is meant to be bind-mounted over this default.
RUN mkdir -p /etc/hydra-umc-detection-hef /opt/hydra/models \
    && echo '[]' > /etc/hydra-umc-detection-hef/registry.json \
    && chown -R hydra:hydra /etc/hydra-umc-detection-hef /opt/hydra/models
USER hydra

EXPOSE 8093
ENTRYPOINT ["hydra-umc-detection-hef"]
CMD ["serve", "--addr", "0.0.0.0", "--port", "8093", "--registry", "/etc/hydra-umc-detection-hef/registry.json", "--models-dir", "/opt/hydra/models"]

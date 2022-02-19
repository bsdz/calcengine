FROM python:3.10-slim as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    PIPX_VERSION=1.0.0 \
    POETRY_VERSION=1.1.13 \
    USER_ID=1000 \
    GROUP_ID=1000 \
    USER_NAME=worker \
    GROUP_NAME=worker

# set up worker, map id to host id
# also add docker group and add user to group
# in case we want to control containers from within.
RUN groupadd -g ${GROUP_ID} ${GROUP_NAME} &&\
    useradd -m -l -s /bin/bash -u ${USER_ID} -g ${GROUP_NAME} ${USER_NAME} &&\
    install -d -m 0755 -o ${USER_NAME} -g ${GROUP_NAME} /env &&\
    install -d -m 0755 -o ${USER_NAME} -g ${GROUP_NAME} /app &&\
    groupadd -g 998 docker &&\
    usermod -aG docker ${USER_NAME}

# Avoid warnings by switching to noninteractive
ENV DEBIAN_FRONTEND=noninteractive

# Use apt cache if specified
ARG APT_CACHE_PROXY_URL
RUN if [ ! -z "$APT_CACHE_PROXY_URL" ]; then \
    echo "Acquire::http { Proxy \"$APT_CACHE_PROXY_URL\"; };" >> /etc/apt/apt.conf.d/01proxy \
    ; fi

# install base packages
RUN apt-get update \
    && apt-get install -y -q --no-install-recommends \
        pyqt5-dev-tools \
        qttools5-dev-tools \
    #
    # Clean up
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /tmp/*.deb \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/archives/*

# Switch back to dialog for any ad-hoc use of apt-get
ENV DEBIAN_FRONTEND=dialog

# switch to worker, install poetry
USER worker

ARG PIP_INDEX_URL=https://pypi.python.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ARG PIP_TRUSTED_HOST=pypi.python.org
ENV PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

ENV PATH="${PATH}:/home/${USER_NAME}/.local/bin"
RUN pip install --user "pipx==$PIPX_VERSION" && \
    pipx install "poetry==$POETRY_VERSION" && \
    poetry config experimental.new-installer false


# builder
#
FROM base as builder

ARG VENV_NAME=base

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=off

RUN python -m venv --prompt "$VENV_NAME" /env

ENV VIRTUAL_ENV /env
ENV PATH /env/bin:$PATH

WORKDIR /app
COPY --chown=${USER_NAME}:${GROUP_NAME} . /app

RUN poetry install --no-interaction --no-ansi --extras "demo"

ENV QT_DEBUG_PLUGINS=0

CMD python demo/spreadsheet/main.py

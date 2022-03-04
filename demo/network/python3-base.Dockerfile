FROM python:3 as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
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
    vim \
    wget \
    curl \
    netcat \
    libpq-dev \
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
RUN pip install --user pipx && \
    pipx install poetry && \
    poetry config experimental.new-installer false


# builder
#
FROM base as builder

ARG SSH_PRIVATE_KEY
RUN if [ ! -z "$SSH_PRIVATE_KEY" ]; then \
    echo Installing private key && \
    mkdir --mode 700 ~/.ssh/ && \
    echo "${SSH_PRIVATE_KEY}" > ~/.ssh/id_rsa && \
    chmod 600 ~/.ssh/id_rsa && \
    touch ~/.ssh/known_hosts && \
    chmod 644 ~/.ssh/known_hosts && \
    ssh-keyscan github.com >> ~/.ssh/known_hosts \
    ; fi

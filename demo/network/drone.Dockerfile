FROM scanner-python3-base

ARG VENV_NAME=base

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=off

RUN python -m venv --prompt "$VENV_NAME" /env

ENV VIRTUAL_ENV /env
ENV PATH /env/bin:$PATH

WORKDIR /app
COPY --chown=${USER_NAME}:${GROUP_NAME} ./calcengine ./calcengine
COPY --chown=${USER_NAME}:${GROUP_NAME} ./demo ./demo

RUN cd /app/demo/network && pip install -r requirements.txt

#CMD python /app/demo/network/drone.py
ENV PYTHONPATH=/app
CMD rpyc_classic.py --host 0.0.0.0 --port 18812

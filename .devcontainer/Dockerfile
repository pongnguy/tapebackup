FROM ubuntu:22.04 as base
ENV PYTHONUNBUFFERED=1
#ENV PYTHONHASHSEED=0

RUN --mount=type=cache,target=/var/lib/apt/lists \
  apt-get -y install swig build-essential python3-dev
RUN --mount=type=cache,target=/var/lib/apt/lists \
  apt-get -y install git

#COPY --from=build /root/miniconda/envs/FinRL4 /root/miniconda/envs/FinRL4
# Update workspace without having to reinstall FinRL
RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache/apt \
    apt-get update && \
    apt-get install -y parallel
RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache/apt \
  apt-get install -y apt-transport-https ca-certificates gnupg curl && \
  curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
  apt-get update && apt-get install -y google-cloud-cli
RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache/apt \
  apt-get install -y python3-pip
RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache/apt \
  pip3 install google-cloud-storage
#COPY . /workspace
#RUN --mount=type=secret,id=gcloud.json \
#  #gcloud auth activate-service-account --key-file=/run/secrets/gcloud.json && \
#  mkdir -p /root/.keys/ &&\
#  cp /run/secrets/gcloud.json /root/.keys/gcloud.json
#  #gcloud auth application-default login
#ENV GOOGLE_APPLICATION_CREDENTIALS="/root/.keys/gcloud.json"
#COPY ./examples /workspace/examples
#RUN --mount=type=cache,target=/root/.cache/pip \
#    pip install chardet cchardet
#RUN --mount=type=cache,target=/root/.cache/pip \
#    pip install sqlalchemy-cockroachdb
#RUN mamba install -y graypy

#HEALTHCHECK --interval=30s --timeout=3s \
#  CMD curl -f http://localhost/ || exit 1
#WORKDIR /workspace
#ENTRYPOINT ["mamba", "run", "--no-capture-output", "-n", "FinRL4", "/bin/bash", "-c", "parallel -j $N_PROCESSES -u python3 ::: $(seq $N_PROCESSES | xargs -I{} echo 'examples/Stock_NeurIPS2018_optuna.py') && echo 'spawned $N_PROCESSES of examples/Stock_NeurIPS2018_optuna.py'"]
#ENTRYPOINT ["mamba", "run", "--no-capture-output", "-n", "FinRL4", "/bin/bash", "-c", "parallel -j $N_PROCESSES -u python3 ::: $(seq $N_PROCESSES | xargs -I{} echo 'FinRL_PaperTrading_Demo_refactored.py')"]

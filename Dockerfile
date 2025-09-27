# syntax=docker/dockerfile:1
#
# ===========================================================================
# 'prereqs' stage:  install dev tools packages + soliplex requirements
# ===========================================================================
#
# Derived from: https://docs.docker.com/language/python/build-images/
#
# Prepare the pip download cache / lock file
# ------------------------------------------
#
# Run the `pre_prereqs_container.sh` script, which will populate two
# things we use below:
#
# - `./pip-download` is a directory, caching files from PyPI for the
#   dependencies of `soliplex`.  We will mount this into the build
#   context below.
#
# - 'pylock.toml' a lock file from the downloaded package set
#    We will convert it to a 'requirements.txt' file during the 'prereqs'
#    build below.
#
# Build the image
# ---------------
#
# $ docker build --target prereqs --tag soliplex-prereqs .
#
# Run the default command (bash) for the image
# --------------------------------------------
#
# $ docker run --rm -it soliplex-prereqs
#

FROM python:3.13.7-slim-trixie AS prereqs

# Install system-level build dependencies
RUN \
  --mount=type=bind,target=/pip-download,source=pip-download,rw \
  apt-get update && \
  apt-get install -y \
    curl \
    gpg \
    apt-transport-https \
    git \
    rsync \
    vim \
    jq \
    && \
  pip3 install --cache-dir=/cache --root-user-action=ignore --upgrade pip

# Convert the 'pylock.toml' file generated in the pre-Docker prep phase
# above to a 'requirements.txt' file for our dependencies.
RUN \
  --mount=type=bind,target=lock2requirements.py,source=./bin/lock2requirements.py \
  --mount=type=bind,target=pylock.toml,source=pylock.toml \
  python3 lock2requirements.py > requirements.txt

# Install Python libs from requirements generated from 'pylock.toml'.
RUN \
  --mount=type=bind,target=/pip-download,source=./pip-download,rw \
  pip3 install --root-user-action=ignore \
    --no-index --find-links=/pip-download -r requirements.txt

CMD ["/bin/bash"]

# ===========================================================================
# 'devel' stage:  install 'soliplex' app, tests, etc.
# ===========================================================================
#
# Build the image
# ===============
#
# $ docker build --target devel --tag soliplex-devel .
#
# list all images
# $ docker image ls
#
# run the default command for the image
# $ docker run soliplex-devel
#
# run the default command for an image with:
#   - Remove the container on exit
#   - Map the webapp port back to localhost
#   - Map the host gateway IP as 'host.docker.internal'
#   - Bind-maount the local 'tmp' directory '/uploads'
# $ docker run \
#    --rm \
#    -p 8001:8001 \
#    --add-host=host.docker.internal:host-gateway \
#    --mount type=bind,src=`pwd`/example,target=/installation \
#    soliplex-devel

FROM prereqs AS devel

WORKDIR /soliplex

RUN \
  --mount=type=bind,target=/soliplex,source=.,rw \
    pip3 install --root-user-action=ignore -e . && \
    pip3 install --root-user-action=ignore -e .  --group dev && \
#   pip3 install --root-user-action=ignore -e .  --group tui \
    pip3 install --root-user-action=ignore -e .  --group docs

RUN \
    git config --global --add safe.directory /soliplex

VOLUME ["/installation"]

CMD ["soliplex-cli serve"]

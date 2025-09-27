#! /bin/bash
#=============================================================================
# Prepare to build 'soliplex-prereqs' image
#=============================================================================
#
# Create the download cache (OK if it exists)
set -x
DOWNLOAD_CACHE="$(pwd)/pip-download"
mkdir -p $DOWNLOAD_CACHE

#----------------------------------------------------------------------------
# Download dependencies
#----------------------------------------------------------------------------
#
# Work around a dep graph issue
#
python3.13 -m pip download -d $DOWNLOAD_CACHE cython

python3.13 -m pip download -d $DOWNLOAD_CACHE .
python3.13 -m pip download -d $DOWNLOAD_CACHE .  --group dev
python3.13 -m pip download -d $DOWNLOAD_CACHE .  --group docs
#
# Does not exist yet on 'main'
#
#python3.13 -m pip download -d $DOWNLOAD_CACHE .  --group tui

# Generate a lockfile for dependencies
#
# We will convert it to a 'requirements.txt' while building the
# 'soliplex-prereqs' image.
#
python3.13 -m pip lock --no-index --find-links $DOWNLOAD_CACHE -e .

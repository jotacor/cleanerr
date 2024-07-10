#!/usr/bin/env python3

from config import Config
from delete_movies import DeleteMovies
from delete_tv import DeleteTv
from downloadstation import DownloadStation
import logging as log
import sys
import os

def app():
    log.basicConfig(format='[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%dT%H:%M:%S', level=os.getenv('LOG_LEVEL', 'WARN'), stream=sys.stdout)
    log.info("Initiating...")
    config = Config()

    dmu = DeleteMovies(config)
    dmu.delete_unwatched()

    # dtu = DeleteTv(config)
    # dtu.delete_unwatched()

    # ds = DownloadStation(config)
    # ds.delete_no_tracked()

    log.info("Ending...")

if __name__ == "__main__":
    app()

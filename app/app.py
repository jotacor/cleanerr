#!/usr/bin/env python3

from config import Config
from del_movies_unwatched import DelMoviesUnwatched
from del_tv_unwatched import DelTvUnwatched
from del_movie import DelMovie
from synology_api.filestation import FileStation
from download_station import DownloadStation
import logging as log
import sys
import os

def app():
    log.basicConfig(format='[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%dT%H:%M:%S', level=os.getenv('LOG_LEVEL', 'WARN'), stream=sys.stdout)
    log.info("Initiating...")
    config = Config()

    dmu = DelMoviesUnwatched(config)
    dmu.delete()

    # dtu = DelTvUnwatched(config)
    # dtu.delete()

    # dm = DelMovie(config)
    # dm.delete('title')

    # ds = DownloadStation(config)
    # ds.delete_no_tracked()

    log.info("Ending...")

if __name__ == "__main__":
    app()

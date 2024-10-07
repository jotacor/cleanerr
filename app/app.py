#!/usr/bin/env python3

from config import Config
from delete_movies import DeleteMovies
from delete_tv import DeleteTv
from downloadstation import DownloadStation
from filestation import FileStation
import logging as log
import sys
import os

# TODO: unify DeleteTv and DeleteMovies
def app():
    log.basicConfig(format='[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%dT%H:%M:%S', level=os.getenv('LOG_LEVEL', 'WARN'), stream=sys.stdout)
    log.info("Initiating...")
    config = Config()

    dtu = DeleteTv(config)
    dtu.delete_unwatched()
    dtu.clean_unmonitored_nofile()
    dtu.clean_orphan_files()
    pass

    dmu = DeleteMovies(config)
    dmu.delete_unwatched()
    dmu.clean_unmonitored_nofile()
    dmu.clean_orphan_files()
    pass

    ds = DownloadStation(config)
    ds.delete_no_tracked()
    pass

    fs = FileStation(config)
    fs.delete_empty_dirs(config.fsTvPath)
    pass

    log.info("Ending...")

if __name__ == "__main__":
    app()

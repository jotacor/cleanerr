#!/usr/bin/env python3

from config import Config
from delete_movies import DeleteMovies
from delete_tv import DeleteTv
from downloadstation import DownloadStation
from filestation import FileStation
from delete_base import DeleteBase

log = DeleteBase.get_logger()

def app():
    config = Config()
    log.info("##### DRY RUN ENABLED #####") if config.dryrun else None
    
    log.info("### STARTING")
    
    log.info("## SHOWS")
    dtu = DeleteTv(config)
    dtu.delete_unwatched()
    dtu.clean_unmonitored_nofile()
    dtu.clean_orphan_files()
    pass

    log.info("## MOVIES")
    dmu = DeleteMovies(config)
    dmu.delete_unwatched()
    dmu.clean_unmonitored_nofile()
    dmu.clean_orphan_files()
    pass

    log.info("## CLEAN DOWNLOAD STATION")
    ds = DownloadStation(config)
    ds.delete_no_tracked()
    pass

    log.info("## CLEAN FILESYSTEM")
    fs = FileStation(config)
    fs.delete_empty_dirs(config.fsTvPath)
    pass

    log.info("### ENDING")

if __name__ == "__main__":
    app()

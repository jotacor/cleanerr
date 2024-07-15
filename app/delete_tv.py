import os
import requests
from datetime import datetime
import json
import jq
import sys
import logging as log
from downloadstation import DownloadStation
from filestation import FileStation
from tgram import Telegram
from time import time
import shutil

class DeleteTv:
    def __init__(self, config):
        self.config = config
        self.tg = Telegram(config)
        if not self.config.check("tautulliAPIkey", "sonarrAPIkey"):
            log.error("Required Tautulli/Sonarr API key not set. Cannot continue.")
            sys.exit(1)

        self.config.apicheck(self.config.sonarrHost, self.config.sonarrAPIkey)

        self.protected = []
        if os.path.exists("./protected"):
            with open("./protected", "r") as file:
                while line := file.readline():
                    self.protected.append(int(line.rstrip()))
                    
        try:
            self.protected_tags = [int(i) for i in self.config.sonarrProtectedTags.split(",")]
        except Exception as e:
            self.protected_tags = []

    def clean_unmonitored_nofile(self):
        totalsize = 0
        series = requests.get(f"{self.config.sonarrHost}/api/v3/series?apiKey={self.config.sonarrAPIkey}")
        for serie in series.json():
            if serie['statistics']['episodeFileCount'] == 0 and not serie['monitored'] and not self.config.dryrun:
                requests.delete(
                    f"{self.config.sonarrHost}/api/v3/series/"
                    + str(serie["id"])
                    + f"?apiKey={self.config.sonarrAPIkey}&deleteFiles=true"
                )

        log.info(f"Unmonitored nofile: {totalsize:.2f} GB")

    def clean_orphan_files(self):
        now = time()
        action = 'DELETE'
        if self.config.dryrun:
            action = 'DRYRUN'

        with os.scandir(self.config.fsTvPath) as entries:
            for entry in entries:
                if entry.is_file() and os.stat(entry).st_nlink < 2 and now - os.stat(entry).st_mtime > 4 * 86400:
                    log.info(f"{action} orphan '{entry.name}'")
                    if not self.config.dryrun:
                        os.remove(entry)
                        DownloadStation(self.config).delete_task(entry.name)
                elif entry.is_dir():
                    with os.scandir(entry) as subfiles:
                        if all([os.stat(subfile).st_nlink < 2 for subfile in subfiles]) and now - os.stat(entry).st_mtime > 4 * 86400 and 'eaDir' not in entry.name:
                            log.info(f"{action} orphan dir '{entry.name}'")
                            if not self.config.dryrun:
                                shutil.rmtree(entry)
                                DownloadStation(self.config).delete_task(entry.name)

    def delete_unwatched(self):
        today = round(datetime.now().timestamp())
        totalsize = 0
        tau = requests.get(
            f"{self.config.tautulliHost}/api/v2/?apikey={self.config.tautulliAPIkey}&cmd=get_library_media_info&section_id={self.config.tautulliTvSectionID}&length={self.config.tautulliNumRows}&refresh=true"
        )
        shows = json.loads(tau.text)

        try:
            for series in shows["response"]["data"]["data"]:
                if series["last_played"]:
                    lp = round((today - int(series["last_played"])) / 86400)
                    if lp > self.config.daysSinceLastWatch:
                        totalsize = totalsize + self.__purge(series)
                else:
                    if self.config.daysWithoutWatch > 0:
                        if series["added_at"] and series["play_count"] is None:
                            aa = round((today - int(series["added_at"])) / 86400)
                            if aa > self.config.daysWithoutWatch:
                                totalsize = totalsize + self.__purge(series)
        except Exception as e:
            log.error(
                "There was a problem connecting to Tautulli/Sonarr/Overseerr.\
                 Please double-check that your connection settings and API keys are correct.\n\nError message:\n"
                + str(e)
            )
            sys.exit(1)

        log.info(f"TV unwatched: {totalsize:.2f} GB")

    # TODO: Delete from FS and DS
    def __purge(self, series):
        deletesize = 0
        tvdbid = None

        tau = requests.get(
            f"{self.config.tautulliHost}/api/v2/?apikey={self.config.tautulliAPIkey}&cmd=get_metadata&rating_key={series['rating_key']}"
        )

        guids = jq.compile(".[].data.guids").input(tau.json()).first()

        try:
            if guids:
                tvdbid = [guid for guid in guids if guid.startswith("tvdb://")][0].split("tvdb://", 1)[1]
        except Exception as e:
            log.warn(
                f"{series['title']}: Unexpected GUID metadata from Tautulli. Please refresh your library's metadata in Plex. Using less-accurate 'search mode' for this title. Error message: "
                + str(e)
            )
            guids = []

        son = requests.get(f"{self.config.sonarrHost}/api/v3/series?apiKey={self.config.sonarrAPIkey}")
        try:
            if guids:
                sonarr = (
                    jq.compile(f".[] | select(.tvdbId == {tvdbid})").input(son.json()).first()
                )
            else:
                sonarr = (
                    jq.compile(f".[] | select(.title == \"{series['title']}\")")
                    .input(son.json())
                    .first()
                )

            if sonarr["tvdbId"] in self.protected:
                return deletesize

            if any(e in self.protected_tags for e in sonarr["tags"]):
                return deletesize

            if not self.config.dryrun:
                response = requests.delete(
                    f"{self.config.sonarrHost}/api/v3/series/"
                    + str(sonarr["id"])
                    + f"?apiKey={self.config.sonarrAPIkey}&deleteFiles=true"
                )

            try:
                if not self.config.dryrun and self.config.overseerrAPIkey is not None:
                    headers = {"X-Api-Key": f"{self.config.overseerrAPIkey}"}
                    o = requests.get(
                        f"{self.config.overseerrHost}/api/v1/search/?query=tvdb%3A"
                        + str(sonarr["tvdbId"]),
                        headers=headers,
                    )
                    overseerrid = jq.compile(
                        "[select (.results[].mediainfo.tvdbId = "
                        + str(sonarr["tvdbId"])
                        + ")][0].results[0].mediaInfo.id"
                    ).input(o.json())
                    o = requests.delete(
                        f"{self.config.overseerrHost}/api/v1/media/{overseerrid.text()}",
                        headers=headers,
                    )
            except Exception as e:
                log.error("Overseerr API error. Error message: " + str(e))

            action = "DELETED"
            if self.config.dryrun:
                action = "DRY RUN"

            deletesize = int(sonarr["statistics"]["sizeOnDisk"]) / 1073741824
            log.info(f"{action}: {series["title"]} | {deletesize:.2f} GB  | Radarr ID: {sonarr["id"]}  | TMDB ID: {sonarr["tvdbId"]}")

        except StopIteration:
            pass
        except Exception as e:
            log.error(f"{series["title"]}: {e})")

        return deletesize

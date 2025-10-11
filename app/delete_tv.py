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
        log.info("# UNMONITORED & NOFILES")
        totalsize = 0
        series = requests.get(f"{self.config.sonarrHost}/api/v3/series?apiKey={self.config.sonarrAPIkey}")
        for serie in series.json():
            if serie['statistics']['episodeFileCount'] == 0 and not serie['monitored'] and not self.config.dryrun:
                requests.delete(
                    f"{self.config.sonarrHost}/api/v3/series/"
                    + str(serie["id"])
                    + f"?apiKey={self.config.sonarrAPIkey}&deleteFiles=true"
                )
                deletesize = int(serie["file_size"]) / 1073741824
                totalsize += deletesize
                info_str = f"{serie['title'][:40]}"
                if (padding := 50 - len(info_str)) < 1:
                    padding = 1
                log.info(f"{info_str}{'_' * padding}{deletesize:7.2f} GB")

        totalsize and log.info(f"Total Unmon & No-file: {'_' * 27}{totalsize:.2f} GB")

    def clean_orphan_files(self):
        log.info("# ORPHANS")
        now = time()

        with os.scandir(self.config.fsTvPath) as entries:
            for entry in entries:
                if entry.is_file() and os.stat(entry).st_nlink < 2 and now - os.stat(entry).st_mtime > 4 * 86400:
                    log.info(entry.name)
                    if not self.config.dryrun:
                        os.remove(entry)
                        DownloadStation(self.config).delete_task(entry.name)
                elif entry.is_dir():
                    with os.scandir(entry) as subfiles:
                        if all([os.stat(subfile).st_nlink < 2 for subfile in subfiles]) and now - os.stat(entry).st_mtime > 4 * 86400 and 'eaDir' not in entry.name:
                            log.info(entry.name)
                            if not self.config.dryrun:
                                shutil.rmtree(entry)
                                DownloadStation(self.config).delete_task(entry.name)

    def delete_unwatched(self):
        log.info("# UNWATCHED")
        today = round(datetime.now().timestamp())
        totalsize = 0
        tau = requests.get(
            f"{self.config.tautulliHost}/api/v2/?apikey={self.config.tautulliAPIkey}&cmd=get_library_media_info&section_id={self.config.tautulliTvSectionID}&length={self.config.tautulliNumRows}&refresh=true"
        )
        shows = json.loads(tau.text)

        try:
            for series in shows["response"]["data"]["data"]:
                lp, aa = 0, 0
                if series["last_played"]:
                    lp = round((today - int(series["last_played"])) / 86400)
                if series["added_at"]:
                    aa = round((today - int(series["added_at"])) / 86400)
                if (not series["last_played"] or lp > self.config.daysSinceLastWatch) and aa > self.config.daysSinceAdded:
                    totalsize = totalsize + self.__purge(series)
        except Exception as e:
            log.error(
                "There was a problem connecting to Tautulli/Sonarr/Overseerr.\
                 Please double-check that your connection settings and API keys are correct.\n\nError message:\n"
                + str(e)
            )
            sys.exit(1)

        totalsize and log.info(f"Total Shows {'_' * 38}{totalsize:7.2f} GB")

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
            log.warning(
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

            if sonarr["tvdbId"] in self.protected or any(e in self.protected_tags for e in sonarr["tags"]):
                return deletesize

            if sonarr["status"] == 'continuing':
                return self.__delete_previous_seasons(sonarr, series["title"])

            if sonarr["status"] == 'ended':
                return self.__delete_ended(sonarr, series["title"])

        except StopIteration:
            pass
        except Exception as e:
            log.error(f"{series['title']}: {e}")

        return deletesize


    def __delete_ended(self, sonarr, title):
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


        deletesize = int(sonarr["statistics"]["sizeOnDisk"]) / 1073741824
        info_str = f"{title[:40]}"
        if (padding := 50 - len(info_str)) < 1:
            padding = 1
        log.info(f"{info_str}{'_' * padding}{deletesize:7.2f} GB")
        
        return deletesize


    def __delete_previous_seasons(self, sonarr, title):
        deletesize = 0
        seasons = [
            season
            for season in sonarr.get("seasons", [])
            if season.get("seasonNumber", 0) > 0 and season.get("statistics", {}).get("episodeFileCount", 0) > 0
        ]

        if len(seasons) <= 1:
            return deletesize

        latest_season = max(season["seasonNumber"] for season in seasons)
        seasons_to_delete = [season["seasonNumber"] for season in seasons if season["seasonNumber"] < latest_season]

        if not seasons_to_delete:
            return deletesize

        try:
            episodefiles = requests.get(
                f"{self.config.sonarrHost}/api/v3/episodefile?seriesId={sonarr['id']}&apiKey={self.config.sonarrAPIkey}"
            ).json()
        except Exception as e:
            log.error(f"{title}: Error retrieving episode files: {e}")
            return deletesize

        episodefiles_to_delete = [
            episode for episode in episodefiles if episode.get("seasonNumber") in seasons_to_delete
        ]

        if not episodefiles_to_delete:
            return deletesize

        if not self.config.dryrun:
            for episodefile in episodefiles_to_delete:
                try:
                    requests.delete(
                        f"{self.config.sonarrHost}/api/v3/episodefile/{episodefile['id']}?apiKey={self.config.sonarrAPIkey}"
                    )
                except Exception as e:
                    log.error(f"{title}: Error deleting episode file {episodefile['id']}: {e}")

        total_bytes = sum(file.get("size", 0) for file in episodefiles_to_delete)
        deletesize = total_bytes / 1073741824
        seasons_str = ", S".join(str(season) for season in sorted(seasons_to_delete))
        info_str = f"{title[:40]} S{seasons_str}"
        if (padding := 50 - len(info_str)) < 1:
            padding = 1
        log.info(f"{info_str}{'_' * padding}{deletesize:7.2f} GB")

        return deletesize

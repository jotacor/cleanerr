import json
import os
import shutil
import sys
from datetime import datetime

import jq
import requests
from downloadstation import DownloadStation
from time import time

from delete_base import DeleteBase

log = DeleteBase.get_logger()


class DeleteTv(DeleteBase):
    def __init__(self, config):
        super().__init__(config)
        if not self.config.check("tautulliAPIkey", "sonarrAPIkey"):
            log.error("Required Tautulli/Sonarr API key not set. Cannot continue.")
            sys.exit(1)

        self.config.apicheck(self.config.sonarrHost, self.config.sonarrAPIkey)
        tags = requests.get(f"{self.config.sonarrHost}/api/v3/tag?apikey={self.config.sonarrAPIkey}").json()
        tags_id = {item["label"]: item["id"] for item in tags}
        self.protected_tags = [tags_id.get(tag_name, -1) for tag_name in self.config.sonarrProtectedTags.split(",")]

    def clean_unmonitored_nofile(self):
        self.log("# UNMONITORED & NOFILES")
        series = requests.get(f"{self.config.sonarrHost}/api/v3/series?apiKey={self.config.sonarrAPIkey}")
        for serie in series.json():
            if serie['statistics']['episodeFileCount'] == 0 and not serie['monitored'] and not self.config.dryrun:
                requests.delete(
                    f"{self.config.sonarrHost}/api/v3/series/"
                    + str(serie["id"])
                    + f"?apiKey={self.config.sonarrAPIkey}&deleteFiles=true"
                )
                self.log(serie)

    def clean_orphan_files(self):
        self.log("# ORPHANS")
        now = time()

        with os.scandir(self.config.fsTvPath) as entries:
            for entry in entries:
                if entry.is_file() and os.stat(entry).st_nlink < self.config.filesHardlinks and now - os.stat(entry).st_mtime > self.config.filesMinDays * 86400:
                    self.log(entry.name)
                    if not self.config.dryrun:
                        os.remove(entry)
                        DownloadStation(self.config).delete_task(entry.name)
                elif entry.is_dir():
                    with os.scandir(entry) as subfiles:
                        if all([os.stat(subfile).st_nlink < self.config.filesHardlinks for subfile in subfiles]) and now - os.stat(entry).st_mtime > self.config.filesMinDays * 86400 and 'eaDir' not in entry.name:
                            self.log(entry.name)
                            if not self.config.dryrun:
                                shutil.rmtree(entry)
                                DownloadStation(self.config).delete_task(entry.name)

    def delete_unwatched(self):
        self.log("# UNWATCHED")
        today = round(datetime.now().timestamp())
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
                    self.__purge(series)
        except Exception as e:
            log.error(
                "There was a problem connecting to Tautulli/Sonarr/Overseerr.\
                 Please double-check that your connection settings and API keys are correct.\n\nError message:\n"
                + str(e)
            )
            sys.exit(1)

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

            if any(tag in self.protected_tags for tag in sonarr["tags"]):
                return deletesize

            if sonarr["status"] == 'continuing' and self.config.sonarrDeletePastSeasons:
                return self.__delete_previous_seasons(sonarr)

            if sonarr["status"] == 'ended':
                return self.__delete_ended(sonarr)

        except StopIteration:
            pass
        except Exception as e:
            log.error(f"{series['title']}: {e}")

        return deletesize


    def __delete_ended(self, sonarr):
        if not self.config.dryrun:
            o = requests.delete(
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
                requests.delete(
                    f"{self.config.overseerrHost}/api/v1/media/{overseerrid.text()}",
                    headers=headers,
                )
        except Exception as e:
            log.error("Overseerr API error. Error message: " + str(e))

        self.log(sonarr)

    def __delete_previous_seasons(self, sonarr):
        title = self._clean_title(sonarr)
        seasons = [
            season
            for season in sonarr.get("seasons", [])
            if season.get("seasonNumber", 0) > 0 and season.get("statistics", {}).get("episodeFileCount", 0) > 0
        ]

        if len(seasons) <= 1:
            return

        latest_season = max(season["seasonNumber"] for season in seasons)
        seasons_to_delete = [season["seasonNumber"] for season in seasons if season["seasonNumber"] < latest_season]

        if not seasons_to_delete:
            return

        try:
            episodefiles = requests.get(
                f"{self.config.sonarrHost}/api/v3/episodefile?seriesId={sonarr['id']}&apiKey={self.config.sonarrAPIkey}"
            ).json()
        except Exception as e:
            log.error(f"{title}: Error retrieving episode files: {e}")
            return

        episodefiles_to_delete = [
            episode for episode in episodefiles if episode.get("seasonNumber") in seasons_to_delete
        ]

        if not episodefiles_to_delete:
            return

        if not self.config.dryrun:
            for episodefile in episodefiles_to_delete:
                try:
                    requests.delete(
                        f"{self.config.sonarrHost}/api/v3/episodefile/{episodefile['id']}?apiKey={self.config.sonarrAPIkey}"
                    )
                except Exception as e:
                    log.error(f"{title}: Error deleting episode file {episodefile['id']}: {e}")
            
            self.__unmonitor_previous_seasons(sonarr, seasons_to_delete)

        total_bytes = sum(file.get("size", 0) for file in episodefiles_to_delete)
        deletesize = total_bytes / 1073741824
        seasons_str = ", S".join(str(season) for season in sorted(seasons_to_delete))
        info_str = f"{title} S{seasons_str}"
        self.log(info_str, deletesize, clean_title=False)

        return deletesize


    def __unmonitor_previous_seasons(self, sonarr, seasons):
        updated_seasons = []
        for season in sonarr.get("seasons", []):
            season_copy = {
                key: value
                for key, value in season.items()
                if key != "statistics"
            }
            if season_copy.get("seasonNumber") in seasons:
                season_copy["monitored"] = False
            updated_seasons.append(season_copy)

        excluded_keys = {"statistics", "lastInfoSync", "previousAiring", "nextAiring"}
        series_update = {
            key: value
            for key, value in sonarr.items()
            if key not in excluded_keys
        }
        series_update["seasons"] = updated_seasons

        try:
            requests.put(
                f"{self.config.sonarrHost}/api/v3/series/{sonarr['id']}?apiKey={self.config.sonarrAPIkey}",
                json=series_update,
            )
        except Exception as e:
            log.error(f"{sonarr['title']}: Error updating Sonarr series to unmonitor seasons {seasons}: {e}")

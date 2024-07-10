import os
import requests
from datetime import datetime
import json
import jq
import sys
import logging as log

# TODO: ALL
class DeleteTv:
    def __init__(self, config):
        self.config = config
        if not self.config.check("tautulliAPIkey", "sonarrAPIkey"):
            log.error("ERROR: Required Tautulli/Sonarr API key not set. Cannot continue.")
            sys.exit(1)

        self.config.apicheck(self.config.sonarrHost, self.config.sonarrAPIkey)

        self.protected = []

        try:
            self.protected_tags = [int(i) for i in self.config.sonarrProtectedTags.split(",")]
        except Exception as e:
            self.protected_tags = []

        if os.path.exists("./protected"):
            with open("./protected", "r") as file:
                while line := file.readline():
                    self.protected.append(int(line.rstrip()))

    def delete(self):
        today = round(datetime.now().timestamp())
        totalsize = 0
        r = requests.get(
            f"{config.tautulliHost}/api/v2/?apikey={config.tautulliAPIkey}&cmd=get_library_media_info&section_id={config.tautulliTvSectionID}&length={config.tautulliNumRows}&refresh=true"
        )
        shows = json.loads(r.text)

        try:
            for series in shows["response"]["data"]["data"]:
                if series["last_played"]:
                    lp = round((today - int(series["last_played"])) / 86400)
                    if lp > config.daysSinceLastWatch:
                        totalsize = totalsize + self.__purge(series)
                else:
                    if config.daysWithoutWatch > 0:
                        if series["added_at"] and series["play_count"] is None:
                            aa = round((today - int(series["added_at"])) / 86400)
                            if aa > config.daysWithoutWatch:
                                totalsize = totalsize + self.__purge(series)
        except Exception as e:
            print(
                "ERROR: There was a problem connecting to Tautulli/Sonarr/Overseerr. Please double-check that your connection settings and API keys are correct.\n\nError message:\n"
                + str(e)
            )
            sys.exit(1)

        print("Total space reclaimed: " + str("{:.2f}".format(totalsize)) + "GB")

    def __purge(self, series):
        deletesize = 0
        tvdbid = None

        r = requests.get(
            f"{self.config.tautulliHost}/api/v2/?apikey={self.config.tautulliAPIkey}&cmd=get_metadata&rating_key={series['rating_key']}"
        )

        guids = jq.compile(".[].data.guids").input(r.json()).first()

        try:
            if guids:
                tvdbid = [i for i in guids if i.startswith("tvdb://")][0].split(
                    "tvdb://", 1
                )[1]
        except Exception as e:
            print(
                f"WARNING: {series['title']}: Unexpected GUID metadata from Tautulli. Please refresh your library's metadata in Plex. Using less-accurate 'search mode' for this title. Error message: "
                + str(e)
            )
            guids = []

        f = requests.get(f"{self.config.sonarrHost}/api/v3/series?apiKey={self.config.sonarrAPIkey}")
        try:
            if guids:
                sonarr = (
                    jq.compile(f".[] | select(.tvdbId == {tvdbid})").input(f.json()).first()
                )
            else:
                sonarr = (
                    jq.compile(f".[] | select(.title == \"{series['title']}\")")
                    .input(f.json())
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
                        f"{self.config.overseerrHost}/api/v1/media/" + str(overseerrid.text()),
                        headers=headers,
                    )
            except Exception as e:
                print("ERROR: Overseerr API error. Error message: " + str(e))

            action = "DELETED"
            if self.config.dryrun:
                action = "DRY RUN"

            deletesize = int(sonarr["statistics"]["sizeOnDisk"]) / 1073741824
            print(
                action
                + ": "
                + series["title"]
                + " | "
                + str("{:.2f}".format(deletesize))
                + "GB"
                + " | Sonarr ID: "
                + str(sonarr["id"])
                + " | TVDB ID: "
                + str(sonarr["tvdbId"])
            )
        except StopIteration:
            pass
        except Exception as e:
            print("ERROR: " + series["title"] + ": " + str(e))

        return deletesize

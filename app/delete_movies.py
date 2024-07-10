import os
from datetime import datetime
import json
import requests
import jq
import sys
import logging as log
from downloadstation import DownloadStation
from filestation import FileStation

class DeleteMovies:
    def __init__(self, config):
        self.config = config
        if not self.config.check("tautulliAPIkey", "radarrAPIkey"):
            log.error("Required Tautulli/Radarr API key not set. Cannot continue.")
            sys.exit(1)

        self.config.apicheck(self.config.radarrHost, self.config.radarrAPIkey)
        
        self.protected = []
        if os.path.exists("./protected"):
            with open("./protected", "r") as file:
                while line := file.readline():
                    self.protected.append(int(line.rstrip()))

        try:
            self.protected_tags = [int(i) for i in self.config.radarrProtectedTags.split(",")]
        except Exception as e:
            self.protected_tags = []

    def delete_unwatched(self):
        today = round(datetime.now().timestamp())
        totalsize = 0
        r = requests.get(
            f"{self.config.tautulliHost}/api/v2/?apikey={self.config.tautulliAPIkey}&cmd=get_library_media_info&section_id={self.config.tautulliMovieSectionID}&length={self.config.tautulliNumRows}&refresh=true"
        )
        movies = json.loads(r.text)

        try:
            for movie in movies["response"]["data"]["data"]:
                if movie["last_played"]:
                    lp = round((today - int(movie["last_played"])) / 86400)
                    if lp > self.config.daysSinceLastWatch:
                        totalsize = totalsize + self.__purge(movie)
                else:
                    if self.config.daysWithoutWatch > 0:
                        if movie["added_at"] and movie["play_count"] is None:
                            aa = round((today - int(movie["added_at"])) / 86400)
                            if aa > self.config.daysWithoutWatch:
                                totalsize = totalsize + self.__purge(movie)
        except Exception as e:
            log.error(
                "There was a problem connecting to Tautulli/Radarr/Overseerr. Please double-check that your connection settings and API keys are correct.\n\nError message:\n"
                + str(e)
            )
            sys.exit(1)

        log.info("Total space reclaimed: " + str("{:.2f}".format(totalsize)) + "GB")

    # TODO
    # def clean_unmonitored_nofile(self):
    #  # if not movie['hasFile'] and not movie['monitored']:
    
    def __purge(self, movie):
        deletesize = 0
        tmdbid = None

        t = requests.get(
            f"{self.config.tautulliHost}/api/v2/?apikey={self.config.tautulliAPIkey}&cmd=get_metadata&rating_key={movie['rating_key']}"
        )

        guids = jq.compile(".[].data.guids").input(t.json()).first()
        try:
            if guids:
                tmdbid = [i for i in guids if i.startswith("tmdb://")][0].split(
                    "tmdb://", 1
                )[1]
        except Exception as e:
            log.warn(
                f"{movie['title']}: Unexpected GUID metadata from Tautulli. Please refresh your library's metadata in Plex. Using less-accurate 'search mode' for this title. Error message: "
                + str(e)
            )
            guids = []

        r = requests.get(f"{self.config.radarrHost}/api/v3/movie?apiKey={self.config.radarrAPIkey}")
        try:
            if guids:
                radarr = (
                    jq.compile(f".[] | select(.tmdbId == {tmdbid})").input(r.json()).first()
                )
            else:
                radarr = (
                    jq.compile(f".[] | select(.title == \"{movie['title']}\")")
                    .input(r.json())
                    .first()
                )

            if radarr["tmdbId"] in self.protected:
                return deletesize

            if any(e in self.protected_tags for e in radarr["tags"]):
                return deletesize

            if not self.config.dryrun:
                response = requests.delete(
                    f"{self.config.radarrHost}/api/v3/movie/"
                    + str(radarr["id"])
                    + f"?apiKey={self.config.radarrAPIkey}&deleteFiles=true"
                )
                DownloadStation(self.config).delete_task(radarr['movieFile']['originalFilePath'])
                FileStation(self.config).delete_file(f"{self.config.fsMoviePath}/{radarr['movieFile']['originalFilePath']}")

            try:
                if not self.config.dryrun and self.config.overseerrAPIkey is not None:
                    headers = {"X-Api-Key": f"{self.config.overseerrAPIkey}"}
                    o = requests.get(
                        f"{self.config.overseerrHost}/api/v1/movie/" + str(radarr["tmdbId"]),
                        headers=headers,
                    )
                    overseerr = json.loads(o.text)
                    o = requests.delete(
                        f"{self.config.overseerrHost}/api/v1/media/"
                        + str(overseerr["mediaInfo"]["id"]),
                        headers=headers,
                    )
            except Exception as e:
                log.error("Unable to connect to overseerr. Error message: " + str(e))

            action = "DELETED"
            if self.config.dryrun:
                action = "DRY RUN"

            deletesize = int(movie["file_size"]) / 1073741824
            log.info(
                action
                + ": "
                + movie["title"]
                + " | "
                + str("{:.2f}".format(deletesize))
                + "GB"
                + " | Radarr ID: "
                + str(radarr["id"])
                + " | TMDB ID: "
                + str(radarr["tmdbId"])
            )
        except StopIteration:
            pass
        except Exception as e:
            log.error(f'{movie["title"]}: {str(e)}')

        return deletesize

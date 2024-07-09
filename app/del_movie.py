import sys
import json
import requests
import jq
import argparse
from argparse import RawTextHelpFormatter
import logging as log

class DelMovie:
    def __init__(self, config):
        self.config = config
        if not self.config.check("tautulliAPIkey", "radarrAPIkey"):
            log.error("ERROR: Required Tautulli/Radarr API key not set. Cannot continue.")
            sys.exit(1)

        self.config.apicheck(self.config.radarrHost, self.config.radarrAPIkey)

        parser = argparse.ArgumentParser(
            description="Enter a movie title as an argument to delete a movie from overseerr, radarr, and from the disk.\nDon't worry! You'll be prompted before it does a delete.\nSo that it is properly read, pass your title as:\n\n  --title=\"Search Title\"\n",
            formatter_class=RawTextHelpFormatter,
        )
        parser.add_argument(
            "--title",
            metavar="search title",
            type=str,
            nargs="?",
            help="The title to search for deletion.",
            required=True,
        )
        args = parser.parse_args()
        if not isinstance(args.title, str) or len(args.title) < 1:
            parser.print_help(sys.stderr)
            sys.exit(1)

    def delete(self, title):
        totalsize = 0
        r = requests.get(
            f"{self.config.tautulliHost}/api/v2/?apikey={self.config.tautulliAPIkey}&cmd=get_library_media_info&section_id={self.config.tautulliMovieSectionID}&search={title}&refresh=true"
        )
        movies = json.loads(r.text)

        try:
            if len(movies["response"]["data"]["data"]) == 1:
                movie = movies["response"]["data"]["data"][0]
                confirmation = input(
                    "Movie found:\n"
                    + movie["title"]
                    + " ("
                    + movie["year"]
                    + ")\nDelete it? [N]: "
                )
                if confirmation.lower() == "y":
                    confirmation = 1
                else:
                    confirmation = 0
            elif len(movies["response"]["data"]["data"]) > 1:
                print("[0] Delete nothing")
                for i, movie in enumerate(movies["response"]["data"]["data"], 1):
                    print("[" + str(i) + "] " + movie["title"] + " (" + movie["year"] + ")")
                try:
                    if config.dryrun:
                        print("DRY RUN MODE - no selected movies will be deleted")
                    else:
                        print("*** The selected movie will be deleted ***")
                    confirmation = int(input("Choose a movie to delete [0]: "))
                except:
                    print("No action taken.")
                    sys.exit(0)
            else:
                print("I couldn't find your movie. Try a different search term.")
                sys.exit(0)

            if confirmation > 0:
                try:
                    confirmation = confirmation - 1
                    movie = movies["response"]["data"]["data"][confirmation]
                    print("Total space reclaimed: " + str("{:.2f}".format(self.__purge(movie))) + "GB")
                except Exception as e:
                    print("Couldn't delete movie.\n\n" + str(e))
            else:
                print("No action taken.")
        except Exception as e:
            print(
                "ERROR: There was a problem connecting to Tautulli/Radarr/Overseerr. Please double-check that your connection settings and API keys are correct.\n\nError message:\n"
                + str(e)
            )
            sys.exit(1)

    def __purge(self, movie):
        deletesize = 0
        tmdbid = None

        r = requests.get(
            f"{self.config.tautulliHost}/api/v2/?apikey={self.config.tautulliAPIkey}&cmd=get_metadata&rating_key={movie['rating_key']}"
        )

        guids = jq.compile(".[].data.guids").input(r.json()).first()

        try:
            if guids:
                tmdbid = [i for i in guids if i.startswith("tmdb://")][0].split(
                    "tmdb://", 1
                )[1]
        except Exception as e:
            print(
                f"WARNING: {movie['title']}: Unexpected GUID metadata from Tautulli. Please refresh your library's metadata in Plex. Using less-accurate 'search mode' for this title. Error message: "
                + str(e)
            )
            guids = []

        f = requests.get(f"{self.config.radarrHost}/api/v3/movie?apiKey={self.config.radarrAPIkey}")
        try:
            if guids:
                radarr = (
                    jq.compile(f".[] | select(.tmdbId == {tmdbid})").input(f.json()).first()
                )
            else:
                radarr = (
                    jq.compile(f".[] | select(.title == \"{movie['title']}\")")
                    .input(f.json())
                    .first()
                )
            if not self.config.dryrun:
                response = requests.delete(
                    f"{self.config.radarrHost}/api/v3/movie/"
                    + str(radarr["id"])
                    + f"?apiKey={self.config.radarrAPIkey}&deleteFiles=true"
                )

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
                print("ERROR: Unable to connect to overseerr.")

            action = "DELETED"
            if self.config.dryrun:
                action = "DRY RUN"

            print(
                action
                + ": "
                + movie["title"]
                + " | Radarr ID: "
                + str(radarr["id"])
                + " | TMDB ID: "
                + str(radarr["tmdbId"])
            )
            deletesize = int(movie["file_size"]) / 1073741824
        except StopIteration:
            pass
        except Exception as e:
            print("ERROR: " + movie["title"] + ": " + str(e))

        return deletesize

#!/usr/bin/env python3

from config import Config
from synology_api.downloadstation import DownloadStation
import radarr
import logging as log
import sys
import requests


def app():
    c = Config()
    log.basicConfig(format='[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%dT%H:%M:%S', level=c.log_level, stream=sys.stdout)
    log.info("Initiating...")

    radarrconfig = radarr.Configuration(host=c.radarrHost)
    radarrconfig.api_key['X-Api-Key'] = c.radarrAPIkey
    rdr_movie = radarr.MovieApi(radarr.ApiClient(radarrconfig))
    rdr_history = dict()
    headers = {'X-Api-Key': c.radarrAPIkey, 'accept': 'application/json'}
    eventMovieFileDeleted = 6
    response = requests.get(c.radarrHost+f'/api/v3/history?page=1&pageSize=10&eventType={eventMovieFileDeleted}', headers=headers)
    if response.status_code == 200:
        r = response.json()
        for deleted in r['records']:
            rdr_history.update({deleted['movieId']: deleted['sourceTitle']})
    
    ds = DownloadStation(c.dsIp, c.dsPort, c.dsUser, c.dsPassword, debug=True)
    tlist = ds.tasks_list()
    ds_tasks = dict()
    for task in tlist['data']['tasks']:
        if not any([status for status in task['additional']['tracker'] if status['status'] == 'Success']):
            log.info(f"Deleting '{movie['title']}' not yet in tracker from DownloadStation")
            ds.delete_task(task['id'])
            continue

        ds_tasks.update({task['title']: task['id']})

    movies = rdr_movie.list_movie()
    for movie in movies:
        if not movie['has_file'] and not movie['monitored']:
            filename = rdr_history[movie['id']].split("/")[-1]
            if filename in ds_tasks:
                log.info(f"Deleting '{movie['title']}' from DownloadStation")
                ds.delete_task(ds_tasks[filename])
            else:
                log.warning(f"Movie '{movie['title']}' not found in DownloadStation")
            
            log.info(f"Deleting '{movie['title']}' movie from Radarr")
            rdr_movie.delete_movie(movie['id'])

    log.info("Ending...")

if __name__ == "__main__":
    app()

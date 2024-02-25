#!/usr/bin/env python3

from config import Config
from synology_api.downloadstation import DownloadStation
import radarr
import logging as log
import sys
import requests

def radarr_api(config):
    radarrconfig = radarr.Configuration(host=config.radarrHost)
    radarrconfig.api_key['X-Api-Key'] = config.radarrAPIkey
    rdr_movie_api = radarr.MovieApi(radarr.ApiClient(radarrconfig))
    rdr_deleted = dict()
    headers = {'X-Api-Key': config.radarrAPIkey, 'accept': 'application/json'}
    eventMovieFileDeleted = 6
    response = requests.get(config.radarrHost+f'/api/v3/history?page=1&pageSize=10&eventType={eventMovieFileDeleted}', headers=headers)
    if response.status_code == 200:
        r = response.json()
        for deleted in r['records']:
            rdr_deleted.update({deleted['movieId']: deleted['sourceTitle']})
    
    return rdr_movie_api, rdr_deleted

def download_station(ds):
    all_tasks = ds.tasks_list()
    ds_tasks = dict()
    for task in all_tasks['data']['tasks']:
        if task['status'] == 'error' or ('tracker' in task['additional'] and not any([status for status in task['additional']['tracker'] if status['status'] == 'Success'])):
            log.info(f"Deleting '{task['title']}' not yet in tracker or '{task['status']}' from DownloadStation")
            ds.delete_task(task['id'])
            continue

        ds_tasks.update({task['title']: task['id']})

    return ds_tasks

def clean_deleted_movies(ds, rdr_movie_api, rdr_deleted):
    ds_tasks = download_station(ds)
    movies = rdr_movie_api.list_movie()
    for movie in movies:
        if not movie['has_file'] and not movie['monitored']:
            filename = rdr_deleted[movie['id']].split("/")[-1]
            if filename in ds_tasks:
                log.info(f"Deleting '{movie['title']}' from DownloadStation")
                ds.delete_task(ds_tasks[filename])
            else:
                log.warning(f"Movie '{movie['title']}' not found in DownloadStation")
            
            log.info(f"Deleting '{movie['title']}' movie from Radarr")
            rdr_movie_api.delete_movie(movie['id'])

def app():
    config = Config()
    log.basicConfig(format='[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%dT%H:%M:%S', level=config.log_level, stream=sys.stdout)
    log.info("Initiating...")

    rdr_movie_api, rdr_deleted = radarr_api(config)
    ds = DownloadStation(config.dsIp, config.dsPort, config.dsUser, config.dsPassword, debug=True)

    clean_deleted_movies(ds, rdr_movie_api, rdr_deleted)

    log.info("Ending...")

if __name__ == "__main__":
    app()

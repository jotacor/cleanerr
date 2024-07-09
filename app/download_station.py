from synology_api.downloadstation import DownloadStation as DS
import logging as log


class DownloadStation:
    def __init__(self, config):
        self.ds = DS(config.dsIp, config.dsPort, config.dsUser, config.dsPassword, debug=True)

    def delete_task(self, movie):
        all_tasks = self.ds.tasks_list()
        ds_tasks = dict()
        for task in all_tasks['data']['tasks']:
            ds_tasks.update({task['title']: task['id']})

        if not movie['hasFile'] and not movie['monitored']:
            filename = movie['movieFile']['originalFilePath']
            if filename in ds_tasks:
                log.info(f"Deleting '{movie['title']}' from DownloadStation")
                self.ds.delete_task(ds_tasks[filename])
            else:
                log.warning(f"Movie '{movie['title']}' not found in DownloadStation")
            
            log.info(f"Deleting '{movie['title']}' movie from Radarr")

    def delete_no_tracked(self):
        all_tasks = self.ds.tasks_list()
        for task in all_tasks['data']['tasks']:
            if task['status'] == 'error' or ('tracker' in task['additional'] and not any([status for status in task['additional']['tracker'] if status['status'] == 'Success'])):
                log.info(f"Deleting '{task['title']}' not yet in tracker or '{task['status']}' from DownloadStation")
                self.ds.delete_task(task['id'])

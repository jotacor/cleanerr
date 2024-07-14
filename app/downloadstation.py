from synology_api.downloadstation import DownloadStation as DS
import logging as log


class DownloadStation:
    def __init__(self, config):
        self.config = config
        self.ds = DS(config.dsIp, config.dsPort, config.dsUser, config.dsPassword, debug=False)

    def delete_task(self, taskname):
        all_tasks = self.ds.tasks_list()
        ds_tasks = dict()
        for task in all_tasks['data']['tasks']:
            ds_tasks.update({task['title']: task['id']})

        log.info(f"Deleting '{taskname}' from DownloadStation")
        r = self.ds.delete_task(ds_tasks[taskname])
        if r['data'][0]['error'] != 0:
            log.warning(f"Task '{taskname}' not found in DownloadStation")

    def delete_no_tracked(self):
        all_tasks = self.ds.tasks_list()
        for task in all_tasks['data']['tasks']:
            if task['status'] == 'error' or ('tracker' in task['additional'] and not any([status for status in task['additional']['tracker'] if status['status'] == 'Success'])):
                log.info(f"Deleting '{task['title']}' not yet in tracker or '{task['status']}' from DownloadStation")
                if not self.config.dryrun:
                    self.ds.delete_task(task['id'])

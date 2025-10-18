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

        if taskname not in ds_tasks:
            log.debug(f"DS NOT FOUND: '{taskname}'")
        else:
            r = self.ds.delete_task(ds_tasks[taskname])
            if r['data'][0]['error'] != 0:
                log.debug(f"DS NOT FOUND: '{taskname}'")
            else:
                log.debug(f"DELETED DS: '{taskname}'")

    def delete_no_tracked(self):
        all_tasks = self.ds.tasks_list()
        for task in all_tasks['data']['tasks']:
            has_tracker_info = 'tracker' in task['additional']
            tracker_error = task['status'] == 'error'
            valid_tracker_status = [
                'Success',
                '',
                'Could not connect to tracker',
                'Please respect the min interval'
            ]
            tracker_statuses = task['additional']['tracker'] if has_tracker_info else []

            tracker_ok = any(
                valid_status in tracker_statuses for valid_status in valid_tracker_status
            )

            if tracker_error or (has_tracker_info and not tracker_ok):
                log.info(f"DELETED DS TRACKER: '{task['title']}'")
                if not self.config.dryrun:
                    self.ds.delete_task(task['id'])

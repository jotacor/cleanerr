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
            task_status_error = task['status'] == 'error'
            valid_tracker_status = [
                'Success',
                '',
                'Could not connect to tracker',
                'Please respect the min interval'
            ]

            task_trackers = task['additional'].get('tracker') or []
            task_trackers_ok = any(
                tracker.get('status') in valid_tracker_status
                for tracker in task_trackers
                if isinstance(tracker, dict)
            )

            if task_status_error or (task_trackers and not task_trackers_ok):
                log.info(f"DELETED DS TRACKER: '{task['title']}'")
                if not self.config.dryrun:
                    self.ds.delete_task(task['id'])

from synology_api.filestation import FileStation as FS
import logging as log
from time import time

class FileStation:
    def __init__(self, config):
        self.config = config
        self.fs = FS(config.dsIp, config.fsPort, config.dsUser, config.dsPassword, secure=False, cert_verify=False, dsm_version=7, otp_code=None, interactive_output=False, debug=False)

    def delete_file(self, filename):
        log.debug(f"DELETE FS: '{filename}'")
        self.__delete(filename)

    def delete_file_search(self, directory, file):
        taskid = self.fs.search_start(folder_path=directory, pattern=file)['taskid']
        count = 0
        while not self.fs.get_search_list(taskid)['finished'] or count < 60:
            time.sleep(1)
            count += 1
            pass
        result = self.fs.get_search_list(taskid)
        if result['finished']:
            pass

    def delete_empty_dirs(self, directory):
        filelist = self.fs.get_file_list(directory, filetype='dir', additional='size')
        for file in filelist['data']['files']:
            if file['isdir'] and file['additional']['size'] <= 12:
                name = f"{directory}/{file['name']}"
                log.debug(f"DELETE FS EMPTY DIR: '{name}'")
                self.__delete(f"{name}")
    
    def __delete(self, name):
        try:
            if not self.config.dryrun:
                r = self.fs.delete_blocking_function(name)
        except Exception as e:
            log.error(f"FileStation: {e.error_message}")
from synology_api.filestation import FileStation as FS
import logging as log


class FileStation:
    def __init__(self, config):
        self.fs = FS(config.dsIp, config.fsPort, config.dsUser, config.dsPassword, secure=False, cert_verify=False, dsm_version=7, otp_code=None, debug=True)

    def delete_file(self, filename):
        log.info(f"Deleting '{filename}' from FileStation")
        try:
            r = self.fs.delete_blocking_function(filename)
            pass
        except Exception as e:
            log.error(f"FileStation: {e.error_message}")

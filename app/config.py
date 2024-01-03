import os


class Config:
    def __init__(self):
        self.log_level = os.getenv('LOG_LEVEL', 'WARN')
        self.radarrHost = os.getenv("RADARR", "http://localhost:7878")
        self.radarrAPIkey = os.getenv("RADARR_API")
        self.dsIp = os.getenv("DS_IP", "localhost")
        self.dsPort = os.getenv("DS_PORT", "5001")
        self.dsUser = os.getenv("DS_USER")
        self.dsPassword = os.getenv("DS_PASSWORD")

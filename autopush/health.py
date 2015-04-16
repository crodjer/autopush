from autopush import __version__
from autopush.web import CORSHandler


class StatusHandler(CORSHandler):
    def get(self):
        self.write({
            "status": "OK",
            "version": __version__
        })

from cyclone.web import (HTTPError, RequestHandler)


class CORSHandler(RequestHandler):
    def options(self, *args, **kwargs):
        if not self.ap_settings.cors:
            raise HTTPError(405)

    def head(self, *args, **kwargs):
        if not self.ap_settings.cors:
            raise HTTPError(405)

    def set_default_headers(self):
        if self.ap_settings.cors:
            self.set_header("Access-Control-Allow-Origin", "*")
            self.set_header("Access-Control-Allow-Methods",
                            ",".join(self.SUPPORTED_METHODS))

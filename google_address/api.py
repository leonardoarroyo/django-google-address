from google_address import helpers
import requests


class GoogleAddressApi:
    url = 'https://maps.googleapis.com/maps/api/geocode/json?address={address}'
    key = None

    def __init__(self):
        # Set key
        self.key = helpers.get_settings().get("API_KEY", None)

        # Set language
        self.language = helpers.get_settings().get("API_LANGUAGE", "en_US")

    def _get_url(self):
        url = self.url

        if self.key:
            url = "{}&key={}".format(url, self.key)

        if self.language:
            url = "{}&language={}".format(url, self.language)

        return url

    def query(self, raw):
        url = self._get_url().format(address=raw)

        r = requests.get(url)
        data = r.json()
        return data

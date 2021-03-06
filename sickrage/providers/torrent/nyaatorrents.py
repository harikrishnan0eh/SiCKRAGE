# Author: Mr_Orange
# URL: https://sickrage.ca
#
# This file is part of SickRage.
#
# SickRage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickRage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickRage.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import sickrage
from sickrage.core.caches.tv_cache import TVCache
from sickrage.core.helpers import convert_size, try_int
from sickrage.providers import TorrentProvider


class NyaaProvider(TorrentProvider):
    def __init__(self):
        super(NyaaProvider, self).__init__("NyaaTorrents", 'https://nyaa.si', False)

        self.supports_absolute_numbering = True
        self.anime_only = True
        self.confirmed = False

        self.minseed = None
        self.minleech = None

        self.cache = TVCache(self, min_time=20)

    def search(self, search_strings, age=0, ep_obj=None, **kwargs):
        """
        Search a provider and parse the results.

        :param search_strings: A dict with mode (key) and the search value (value)
        :param age: Not used
        :param ep_obj: Not used
        :returns: A list of search results (structure)
        """
        results = []

        # Search Params
        search_params = {
            'page': 'rss',
            'c': '1_0',  # All Anime
            'f': 0,  # No filter
            'q': '',
        }

        for mode in search_strings:
            sickrage.app.log.debug('Search mode: {}'.format(mode))

            if self.confirmed:
                search_params['f'] = 2  # Trusted only
                sickrage.app.log.debug('Searching only confirmed torrents')

            for search_string in search_strings[mode]:
                if mode != 'RSS':
                    sickrage.app.log.debug('Search string: {}'.format(search_string))
                    search_params['q'] = search_string

                data = self.cache.getRSSFeed(self.urls['base_url'], params=search_params)
                if not data:
                    sickrage.app.log.debug('No data returned from provider')
                    continue
                if not data.get('entries'):
                    sickrage.app.log.debug('Data returned from provider does not contain any {}torrents'.format(
                        'confirmed ' if self.confirmed else ''))
                    continue

                results += self.parse(data['entries'], mode)

        return results

    def parse(self, data, mode, **kwargs):
        """
        Parse search results from data
        :param data: response data
        :param mode: search mode
        :return: search results
        """

        results = []

        for item in data:
            try:
                title = item['title']
                download_url = item['link']
                if not all([title, download_url]):
                    continue

                seeders = try_int(item['nyaa_seeders'])
                leechers = try_int(item['nyaa_leechers'])

                size = convert_size(item['nyaa_size'], -1, units=['B', 'KIB', 'MIB', 'GIB', 'TIB', 'PIB'])

                results += [
                    {'title': title, 'link': download_url, 'size': size, 'seeders': seeders, 'leechers': leechers}
                ]

                if mode != 'RSS':
                    sickrage.app.log.debug("Found result: {}".format(title))
            except Exception:
                sickrage.app.log.error('Failed parsing provider')

        return results

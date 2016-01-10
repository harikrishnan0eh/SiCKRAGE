# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: https://sickrage.tv
# Git: https://github.com/SiCKRAGETV/SickRage.git
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

import datetime
import logging
import operator
import re
import threading
import traceback

from tornado import gen

import db
import helpers
import sickbeard
from common import DOWNLOADED, SNATCHED, SNATCHED_PROPER, Quality, cpu_presets
from name_parser.parser import NameParser, InvalidNameException, InvalidShowException
from search import pickBestResult, snatchEpisode
from sickbeard.exceptions import AuthException
from sickbeard.providers import sortedProviderDict
from sickrage.show.History import History


class ProperSearcher(object):
    def __init__(self, *args, **kwargs):
        self.name = "PROPERSEARCHER"
        self.amActive = False

    def run(self, force=False):
        """
        Start looking for new propers
        :param force: Start even if already running (currently not used, defaults to False)
        """
        if self.amActive:
            return

        logging.info("Beginning the search for new propers")

        self.amActive = True

        propers = self._getProperList()

        if propers:
            self._downloadPropers(propers)

        self._set_lastProperSearch(datetime.datetime.today().toordinal())

        run_at = ""
        if None is sickbeard.properSearcher.start_time:
            run_in = sickbeard.properSearcher.lastRun + sickbeard.properSearcher.cycleTime - datetime.datetime.now()
            hours, remainder = divmod(run_in.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            run_at = ", next check in approx. " + (
                "%dh, %dm" % (hours, minutes) if 0 < hours else "%dm, %ds" % (minutes, seconds))

        logging.info("Completed the search for new propers%s" % run_at)

        self.amActive = False

    def _getProperList(self):
        """
        Walk providers for propers
        """
        propers = {}

        search_date = datetime.datetime.today() - datetime.timedelta(days=2)

        # for each provider get a list of the
        origThreadName = threading.currentThread().name
        for providerID, providerObj in {k: v for k, v in sortedProviderDict(sickbeard.RANDOMIZE_PROVIDERS).items()
                                        if v.isActive}.items():

            threading.currentThread().name = origThreadName + " :: [" + providerObj.name + "]"
            logging.info("Searching for any new PROPER releases from " + providerObj.name)

            try:
                curPropers = providerObj.findPropers(search_date)
            except AuthException as e:
                logging.debug("Authentication error: {}".format(e))
                continue
            except Exception as e:
                logging.debug("Error while searching " + providerObj.name + ", skipping: {}".format(e))
                logging.debug(traceback.format_exc())
                continue

            # if they haven't been added by a different provider than add the proper to the list
            for x in curPropers:
                if not re.search(r'(^|[\. _-])(proper|repack)([\. _-]|$)', x.name, re.I):
                    logging.debug('findPropers returned a non-proper, we have caught and skipped it.')
                    continue

                name = self._genericName(x.name)
                if not name in propers:
                    logging.debug("Found new proper: " + x.name)
                    x.provider = providerObj
                    propers[name] = x

            threading.currentThread().name = origThreadName

        # take the list of unique propers and get it sorted by
        sortedPropers = sorted(propers.values(), key=operator.attrgetter('date'), reverse=True)
        finalPropers = []

        for curProper in sortedPropers:

            try:
                myParser = NameParser(False)
                parse_result = myParser.parse(curProper.name)
            except InvalidNameException:
                logging.debug("Unable to parse the filename " + curProper.name + " into a valid episode")
                continue
            except InvalidShowException:
                logging.debug("Unable to parse the filename " + curProper.name + " into a valid show")
                continue

            if not parse_result.series_name:
                continue

            if not parse_result.episode_numbers:
                logging.debug(
                        "Ignoring " + curProper.name + " because it's for a full season rather than specific episode")
                continue

            logging.debug(
                    "Successful match! Result " + parse_result.original_name + " matched to show " + parse_result.show.name)

            # set the indexerid in the db to the show's indexerid
            curProper.indexerid = parse_result.show.indexerid

            # set the indexer in the db to the show's indexer
            curProper.indexer = parse_result.show.indexer

            # populate our Proper instance
            curProper.show = parse_result.show
            curProper.season = parse_result.season_number if parse_result.season_number is not None else 1
            curProper.episode = parse_result.episode_numbers[0]
            curProper.release_group = parse_result.release_group
            curProper.version = parse_result.version
            curProper.quality = Quality.nameQuality(curProper.name, parse_result.is_anime)
            curProper.content = None

            # filter release
            bestResult = pickBestResult(curProper, parse_result.show)
            if not bestResult:
                logging.debug("Proper " + curProper.name + " were rejected by our release filters.")
                continue

            # only get anime proper if it has release group and version
            if bestResult.show.is_anime:
                if not bestResult.release_group and bestResult.version == -1:
                    logging.debug("Proper " + bestResult.name + " doesn't have a release group and version, ignoring it")
                    continue

            # check if we actually want this proper (if it's the right quality)
            myDB = db.DBConnection()
            sqlResults = myDB.select("SELECT status FROM tv_episodes WHERE showid = ? AND season = ? AND episode = ?",
                                     [bestResult.indexerid, bestResult.season, bestResult.episode])
            if not sqlResults:
                continue

            # only keep the proper if we have already retrieved the same quality ep (don't get better/worse ones)
            oldStatus, oldQuality = Quality.splitCompositeStatus(int(sqlResults[0][b"status"]))
            if oldStatus not in (DOWNLOADED, SNATCHED) or oldQuality != bestResult.quality:
                continue

            # check if we actually want this proper (if it's the right release group and a higher version)
            if bestResult.show.is_anime:
                myDB = db.DBConnection()
                sqlResults = myDB.select(
                        "SELECT release_group, version FROM tv_episodes WHERE showid = ? AND season = ? AND episode = ?",
                        [bestResult.indexerid, bestResult.season, bestResult.episode])

                oldVersion = int(sqlResults[0][b"version"])
                oldRelease_group = (sqlResults[0][b"release_group"])

                if oldVersion > -1 and oldVersion < bestResult.version:
                    logging.info(
                        "Found new anime v" + str(bestResult.version) + " to replace existing v" + str(oldVersion))
                else:
                    continue

                if oldRelease_group != bestResult.release_group:
                    logging.info(
                        "Skipping proper from release group: " + bestResult.release_group + ", does not match existing release group: " + oldRelease_group)
                    continue

            # if the show is in our list and there hasn't been a proper already added for that particular episode then add it to our list of propers
            if bestResult.indexerid != -1 and (bestResult.indexerid, bestResult.season, bestResult.episode) not in map(
                    operator.attrgetter('indexerid', 'season', 'episode'), finalPropers):
                logging.info("Found a proper that we need: " + str(bestResult.name))
                finalPropers.append(bestResult)

        return finalPropers

    def _downloadPropers(self, properList):
        """
        Download proper (snatch it)

        :param properList:
        """

        for curProper in properList:

            historyLimit = datetime.datetime.today() - datetime.timedelta(days=30)

            # make sure the episode has been downloaded before
            myDB = db.DBConnection()
            historyResults = myDB.select(
                    "SELECT resource FROM history " +
                    "WHERE showid = ? AND season = ? AND episode = ? AND quality = ? AND date >= ? " +
                    "AND action IN (" + ",".join([str(x) for x in Quality.SNATCHED + Quality.DOWNLOADED]) + ")",
                    [curProper.indexerid, curProper.season, curProper.episode, curProper.quality,
                     historyLimit.strftime(History.date_format)])

            # if we didn't download this episode in the first place we don't know what quality to use for the proper so we can't do it
            if len(historyResults) == 0:
                logging.info(
                        "Unable to find an original history entry for proper " + curProper.name + " so I'm not downloading it.")
                continue

            else:

                # make sure that none of the existing history downloads are the same proper we're trying to download
                clean_proper_name = self._genericName(helpers.remove_non_release_groups(curProper.name))
                isSame = False
                for curResult in historyResults:
                    # if the result exists in history already we need to skip it
                    if self._genericName(helpers.remove_non_release_groups(curResult[b"resource"])) == clean_proper_name:
                        isSame = True
                        break
                if isSame:
                    logging.debug("This proper is already in history, skipping it")
                    continue

                # get the episode object
                epObj = curProper.show.getEpisode(curProper.season, curProper.episode)

                # make the result object
                result = curProper.provider.getResult([epObj])
                result.show = curProper.show
                result.url = curProper.url
                result.name = curProper.name
                result.quality = curProper.quality
                result.release_group = curProper.release_group
                result.version = curProper.version
                result.content = curProper.content

                # snatch it
                snatchEpisode(result, SNATCHED_PROPER)
                gen.sleep(cpu_presets[sickbeard.CPU_PRESET])

    def _genericName(self, name):
        return name.replace(".", " ").replace("-", " ").replace("_", " ").lower()

    def _set_lastProperSearch(self, when):
        """
        Record last propersearch in DB

        :param when: When was the last proper search
        """

        logging.debug("Setting the last Proper search in the DB to " + str(when))

        myDB = db.DBConnection()
        sqlResults = myDB.select("SELECT * FROM info")

        if len(sqlResults) == 0:
            myDB.action("INSERT INTO info (last_backlog, last_indexer, last_proper_search) VALUES (?,?,?)",
                        [0, 0, str(when)])
        else:
            myDB.action("UPDATE info SET last_proper_search=" + str(when))

    @staticmethod
    def _get_lastProperSearch():
        """
        Find last propersearch from DB
        """

        myDB = db.DBConnection()
        sqlResults = myDB.select("SELECT * FROM info")

        try:
            last_proper_search = datetime.date.fromordinal(int(sqlResults[0][b"last_proper_search"]))
        except:
            return datetime.date.fromordinal(1)

        return last_proper_search

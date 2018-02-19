# This file is part of WSRC.
#
# WSRC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# WSRC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WSRC.  If not, see <http://www.gnu.org/licenses/>.

import cookielib
import httplib2
import logging
import urllib
import urllib2

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

def get_url_params(url):
    "Return the params from the url as a dict. Does not support multi-valued parameters"
    base, query = urllib.splitquery(url)
    params = query.split("&")
    return dict([urllib.splitvalue(p) for p in params])

def get_content(url, params, headers=None):
    url += "?" + urllib.urlencode(params)
    LOGGER.info("Fetching {url}".format(**locals()))
    opener = httplib2.Http()
    (resp_headers, content) = opener.request(url, "GET", headers=headers)
    return content

class MyHTTPRedirectHandler(urllib2.HTTPRedirectHandler):
    def __init__(self):
        self.redirections = []
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirections.append([code, msg, headers, newurl])
        return urllib2.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)
    def clear(self):
        self.redirections = []

class SimpleHttpClient:
    "Simple httpclient which keeps session cookies and does not follow redirect requests"
    def __init__(self, base_url):
        self.base_url = base_url
        self.cookiejar = cookielib.CookieJar()
        self.redirect_recorder = MyHTTPRedirectHandler()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookiejar), self.redirect_recorder)

    def request(self, selector, params=None, timeout=None):
        """Make a request for the given selector. This method returns a file like object as specified by urllib2.urlopen()"""
        url = self.base_url + selector
        if params is not None:
            params = urllib.urlencode(params)
        LOGGER.debug("opening url %(url)s, params: %(params)s" % locals())
        self.redirect_recorder.clear()
        fh = self.opener.open(url, params, timeout)
        return fh

    def get(self, selector, params=None, timeout=None):
        """Make a GET request for the given selector. This method returns a file like object as specified by urllib2.urlopen()"""
        if params is not None:
            params = urllib.urlencode(params)
            selector = "%s?%s" % (selector, params)
        return self.request(selector, None, timeout)

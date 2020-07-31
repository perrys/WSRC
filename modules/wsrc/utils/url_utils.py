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
import json
import logging
import urllib
import urllib2

import httplib2

LOGGER = logging.getLogger(__name__)


def get_url_params(url):
    "Return the params from the url as a dict. Does not support multi-valued parameters"
    base, query = urllib.splitquery(url)
    params = query.split("&")
    return dict([urllib.splitvalue(p) for p in params])


def get_content(url, params, headers=None):
    url += "?" + urllib.urlencode(params)
    LOGGER.debug("Fetching {url}".format(**locals()))
    opener = httplib2.Http()
    (resp_headers, content) = opener.request(url, "GET", headers=headers)
    return content


def request(url, method, body=None, headers=None):
    LOGGER.debug("%s %s: %s", method, url, body)
    opener = httplib2.Http()
    return opener.request(url, method, headers=headers, body=body)


def get_access_token(url, grant_type, client_id, client_secret, redirect_uri=None, temp_access_code=None):
    """
    Retrieve an access token from Oauth-type authorization servers.
    GRANT_TYPE would normally be "client_credentials" or "authorization_code". If it
    is the latter, a temp_auth_code should be provided
    """
    params = {
        "grant_type": grant_type,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if redirect_uri is not None:
        params["redirect_uri"] = redirect_uri
    if temp_access_code is not None:
        params["code"] = temp_access_code
    params = urllib.urlencode(params)
    response = urllib2.urlopen(url, params)
    data = json.load(response)
    return data.get("access_token")


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
        """Make a request for the given selector. This method returns a file like object as
        specified by urllib2.urlopen()"""
        url = self.base_url + selector
        if params is not None:
            params = urllib.urlencode(params)
        LOGGER.debug("opening url %(url)s, params: %(params)s" % locals())
        self.redirect_recorder.clear()
        fh = self.opener.open(url, params, timeout)
        return fh

    def get(self, selector, params=None, timeout=None):
        """Make a GET request for the given selector. This method returns a file like object
        as specified by urllib2.urlopen()"""
        if params is not None:
            params = urllib.urlencode(params)
            selector = "%s?%s" % (selector, params)
        return self.request(selector, None, timeout)

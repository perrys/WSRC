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

"Middleware to set session timeout for each request if cookie is provided"

import logging

LOGGER = logging.getLogger(__name__)

class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    @classmethod
    def get_session_timeout(cls, request):
        session_timeout = request.COOKIES.get("session_timeout")
        try:
            session_timeout = int(session_timeout)
        except ValueError:
            LOGGER.warning("invalid value for session timeout cookie: \"%s\"", session_timeout)        
            session_timeout = None
        return session_timeout
    
    def __call__(self, request):
        session_timeout = self.get_session_timeout(request)
        if session_timeout:
            request.session.set_expiry(session_timeout)
        return self.get_response(request)

    def process_template_response(self, request, response):
        session_timeout = self.get_session_timeout(request)
        if request.user.is_authenticated and session_timeout:
            if response.context_data is None:
                response.context_data = {"session_timeout": session_timeout}
            else:
                response.context_data["session_timeout"] = session_timeout
        return response
        
                
        

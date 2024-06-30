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

"App config for the courts models"

from django.apps import AppConfig

class CourtsModelAppConfig(AppConfig):
    name = 'wsrc.site.courts'
    def ready(self):
        import wsrc.site.settings.settings as settings
        if hasattr(settings, "BOOKING_SYSTEM_STARTS_ENDS"):
            import signal
        

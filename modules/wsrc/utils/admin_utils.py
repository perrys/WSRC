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

"""Utilities for admin classes"""

from django.contrib import admin

class CSVModelAdmin(admin.ModelAdmin):
    "Return results in CSV format if 'as_csv' GET parameter is provided"
    
    def changelist_view(self, request, extra_context=None):
        params = request.GET.copy()
        want_csv = params.pop("as_csv", None)
        if want_csv is not None:
            want_csv = True
            request.GET = params
        response = super(CSVModelAdmin, self).changelist_view(request, extra_context)
        if hasattr(response, "template_name"):
            if want_csv:
                templates = [tname.replace(".html", ".csv") for tname in response.template_name]
                response.template_name = templates
                response["Content-Type"] = 'text/csv'
                response["Content-Disposition"] =  'attachment; filename="{name}_list.csv"'.format(name=self.model._meta.verbose_name)
        return response


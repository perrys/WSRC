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

import xlrd
import datetime

def sheet_to_dict(filename, sheetname):
    """Return the rows in the given spreadsheet as a list of dictionary
       objects. The first row should contain the field names."""

    def convert(ctype, val):
        if ctype == xlrd.XL_CELL_NUMBER or ctype == xlrd.XL_CELL_TEXT:
            return val
        if ctype == xlrd.XL_CELL_EMPTY or ctype == xlrd.XL_CELL_ERROR:
            return None
        if ctype == xlrd.XL_CELL_BOOLEAN:
            return val == 1
        if ctype == xlrd.XL_CELL_DATE:
            (year, month, day, hour, minute, second) = xlrd.xldate_as_tuple(val, book.datemode)
            try:
                return datetime.datetime(year, month, day, hour, minute, second)
            except ValueError:
                return None
        return val

    book = xlrd.open_workbook(filename)
    sheet = book.sheet_by_name(sheetname)
    fieldnames = []
    results = []
    for i in range(0, sheet.nrows):
        row = sheet.row(i)
        rowdict = {}
        for j in range(0, sheet.ncols):
            cell = row[j]
            if i == 0:
                field = None
                if cell.ctype == xlrd.XL_CELL_TEXT:
                    field = cell.value
                fieldnames.append(field)
            else:
                field = fieldnames[j]
                if field is not None:
                    rowdict[field] = convert(cell.ctype, cell.value)
        if i > 0:
            results.append(rowdict)
    return results

if __name__ == "__main__":
    import sys
    rows = sheet_to_dict(sys.argv[1], sys.argv[2])
    for row in rows:
        print row

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

import lxml.etree as etree
import lxml.html

class NullCell:
  "Represents a table cell which has not been initialized"

  def toHtml(self, builder):
    builder.start("td", {})
    builder.end("td")

class Cell:
  "A regular table cell of unit width and height"

  def __init__(self, content, attrs=None, isHeader=False, isHTML=False):
    self.isHTML = isHTML
    if isHTML:
      self.content = content
    else:
      self.content = unicode(content)
    if attrs is None:
      attrs = dict()
    self.attrs = dict(attrs)
    self.isHeader = isHeader
    self.nrows = 1
    self.ncols = 1

  def toHtml(self, builder):
    tag = self.isHeader and "th" or "td"
    node = builder.start(tag, self.attrs)
    if self.isHTML:
      child = lxml.html.fromstring(self.content)
      node.append(child)
    else:
      first = True
      for line in self.content.split("\n"):
        if first:
          first = False
        else:
          builder.start("br", {})
          builder.end("br")
        builder.data(line)
    builder.end(tag)
    
class SpanningCell(Cell):
  "A table cell which spans multiple cell positions"

  @classmethod
  def fromHtml(cls, elt):
    nrows = ncols = 1
    if "rowspan" in elt.attrib:
      nrows = int(elt.attrib["rowspan"])
    if "colspan" in elt.attrib:
      ncols = int(elt.attrib["colspan"])
    return cls(ncols, nrows, elt.text, elt.attrib)
    
  def __init__(self, ncols, nrows, content, attrs=None, isHeader=False, isHTML=False):
    if attrs is None:
      attrs = dict()
    attrs.update({"rowspan": str(nrows or 1), "colspan": str(ncols or 1)})
    Cell.__init__(self, content, attrs, isHeader, isHTML)
    self.nrows = nrows
    self.ncols = ncols

class ChildCell:
  "A placeholder for cell positions which are occupied by a SpanningCell"
  def toHtml(self, builder):
    pass

class AnchorCell(Cell):
  "A table cell of unit width and height which holds a link"

  LINK_PREFIXES = ["http://", "mailto:", "sms:", "tel:"]  

  def toHtml(self, builder):
    tag = self.isHeader and "th" or "td"
    builder.start(tag, self.attrs)
    builder.start("a", {"href": self.content})
    content = self.content
    for l in AnchorCell.LINK_PREFIXES:
      if content.startswith(l):
        content = content[len(l):]
        break;
    builder.data(content)
    builder.end("a")
    builder.end(tag)
    
    
class Table:
  "Encapsulates an HTML table"

  def __init__(self, ncols, nrows, attribs=None):
    self.ncols = ncols
    self.nrows = nrows
    self.cells = [[NullCell() for j in range(0, ncols)] for i in range(0,nrows)]
    self.attribs = attribs or {}

  def addCell(self, c, colOrigin, rowOrigin):
    for i in range(0, c.nrows):
      row = rowOrigin+i
      for j in range(0, c.ncols):
        col = colOrigin+j
        if not isinstance(self.cells[row][col], NullCell):
          sys.stderr.write(etree.tostring(self.toHtml()))
          raise Exception("Attempt to add to non-empty cells, violation at [%(row)d, %(col)d]" % locals())
        if i is 0 and j is 0:
          self.cells[row][col] = c
        else:
          self.cells[row][col] = ChildCell()
    
  def compress(self):
    "Replace multiple null cells on a row with a single empty spanning cell; remove null blocks at the end of a row completely"

    for rownumber, row in enumerate(self.cells):
      blockstart = -1
      def compressBlocks(start, end):
        ncols = end - start
        if ncols > 1:
          cell = SpanningCell(ncols, 1, "")
          self.addCell(cell, start, rownumber)
      for cellnumber, cell in enumerate(row):
        if isinstance(cell, NullCell):
          if blockstart < 0:
            blockstart = cellnumber
        else:
          if blockstart >= 0:
            compressBlocks(blockstart, cellnumber)
            blockstart = -1
      if blockstart >= 0:
        compressBlocks(blockstart, len(row))
            
  def toHtml(self, table_head=None):
    bld = etree.TreeBuilder();
    root = bld.start("table", self.attribs)
    if table_head is not None:
      root.append(lxml.html.fromstring(table_head))
    bld.start("tbody", {})

    i = 0
    while (i < self.nrows):
        bld.start("tr", {})
        j = 0;
        while (j < self.ncols):
            cell = self.cells[i][j]                
            cell.toHtml(bld)
            j += 1
        bld.end("tr")
        i += 1

    bld.end("tbody")
    bld.end("table")
    return bld.close()

  def toHtmlString(self, table_head=None):
    return etree.tostring(self.toHtml(table_head), encoding='UTF-8', method='html')

def formatTable(dataTable, hasHeader = False, col_prefixes=None):
  nrows = len(dataTable)
  ncols = len(dataTable[0])
  table = Table(ncols, nrows)
  for (i,row) in enumerate(dataTable):
    for (j,data) in enumerate(row):
      isHeader = hasHeader and i == 0
      attrs = {"style": "padding-right: 1em;", "align": "left"}
      if not isHeader:
        if col_prefixes is not None and len(data) > 0:
          data = col_prefixes[j] + data
      cls = Cell
      for prefix in AnchorCell.LINK_PREFIXES:
        if data.startswith(prefix):
          cls = AnchorCell
          if prefix in ["sms:", "tel:"]:
            attrs["align"] = "right"
          break
      table.addCell(cls(data, attrs, isHeader=isHeader), j, i)
  return etree.tostring(table.toHtml(), encoding='UTF-8', method='html')

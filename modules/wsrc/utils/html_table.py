import lxml.etree as etree

class NullCell:
  "Represents a table cell which has not been initialized"

  def toHtml(self, builder):
    builder.start("td", {})
    builder.end("td")

class Cell:
  "A regular table cell of unit width and height"

  def __init__(self, content, attrs=None, isHeader=False):
    self.content = unicode(content)
    if attrs is None:
      attrs = dict()
    self.attrs = dict(attrs)
    self.isHeader = isHeader
    self.nrows = 1
    self.ncols = 1

  def toHtml(self, builder):
    tag = self.isHeader and "th" or "td"
    builder.start(tag, self.attrs)
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
    
  def __init__(self, ncols, nrows, content, attrs=None, isHeader=False):
    if attrs is None:
      attrs = dict()
    attrs.update({"rowspan": str(nrows or 1), "colspan": str(ncols or 1)})
    Cell.__init__(self, content, attrs, isHeader)
    self.nrows = nrows
    self.ncols = ncols

class ChildCell:
  "A placeholder for cell positions which are occupied by a SpanningCell"
  def toHtml(self, builder):
    pass
    
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
            
  def toHtml(self):
    bld = etree.TreeBuilder();
    bld.start("table", self.attribs)

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

    bld.end("table")
    return bld.close()

#!/usr/bin/python

import xml.etree.ElementTree as etree
from htmlentitydefs import name2codepoint
from jinja2 import Environment, FileSystemLoader
import sys
import math
import os.path
import os

sys.path.append("./lib")
from Database import DataBase

class NullCell:
  "Represents a table cell which has not been initialized"

  def toHtml(self, builder):
    builder.start("td", {})
    builder.end("td")

class Cell:
  "A regular table cell of unit width and height"

  def __init__(self, content, attrs=None, isHeader=False):
    self.content = str(content)
    if attrs is None:
      attrs = dict()
    self.attrs = dict(attrs)
    self.isHeader = isHeader
    self.nrows = 1
    self.ncols = 1

  def toHtml(self, builder):
    tag = self.isHeader and "th" or "td"
    builder.start(tag, self.attrs)
    builder.data(self.content)
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
  
def renderCompetition(nbrackets, ngames, tournamentId, compressFirstRound):
  colsPerBracket = (4 + ngames)
  ncols = nbrackets * colsPerBracket - 1
  if compressFirstRound:
    nrows = 3 + (1 << nbrackets-2) * 6
  else:
    nrows = 3 + (1 << nbrackets-1) * 6
  table = Table(ncols, nrows, {"class": "bracket", "cellspacing": "0px"})

  topLink    = Cell('', {"class": "toplink"})
  bottomLink = Cell('', {"class": "bottomlink"})

  # first row; nbsp in the top row
  table.addCell(Cell("", None, True), 0, 0)
  for i in range(nbrackets, 0, -1):
    if i == 1:
      content = "Final"
    elif i == 2:
      content = "Semi Finals"
    elif i == 3:
      content = "Quarter Finals"
    else:
      content = "Round %(i)d" % locals()
    table.addCell(SpanningCell(colsPerBracket-2, 1, content, {"class": "roundtitle"}, True),  1+0+(nbrackets-i)*colsPerBracket, 0)
    if i > 1:
      table.addCell(SpanningCell(1, 1, "&nbsp;", {"class": "leftspacer"}, True),  1 + colsPerBracket-2 + (nbrackets-i)*colsPerBracket, 0)
      table.addCell(SpanningCell(1, 1, "&nbsp;", {"class": "rightspacer"}, True), 1 + colsPerBracket-1 + (nbrackets-i)*colsPerBracket, 0)

  # first column; nbsp in the top row
  for i in range(1, nrows):
    content = "&nbsp;"
    if (i > 0): 
      content = ""
    attribs = {'class': "verticalspacer"}
    if i == (nrows-1):
      attribs["class"] += " spacercalc"    
    table.addCell(Cell(content, attribs), 0, i)

  def renderMatch(col, row, bracketIndex, matchIndex, idPrefix):
  
    binomialId = (1<<bracketIndex) + matchIndex  
    class Position:
      def __init__(self, col, row):
        self.row = row
        self.col = col

    p = Position(col, row)

    def addToRow(cls, content="", id=None):
      attrs = {"class": cls}
      if id is not None: attrs["id"] = id
      c = SpanningCell(1, 2, str(content), attrs)
      table.addCell(c, p.col, p.row)
      p.col += c.ncols
      return c
    addToRow("seed ui-corner-tl", "&nbsp;")
    addToRow("player", "&nbsp;", "match_%(idPrefix)s_%(binomialId)d_t" % locals())
    for ii in range(0, ngames):
      last = addToRow("score", "&nbsp;")
    last.attrs["class"] += " ui-corner-tr"

    p.col = col
    p.row += 2
    addToRow("seed ui-corner-bl", "&nbsp;")
    addToRow("player", "&nbsp;", "match_%(idPrefix)s_%(binomialId)d_b" % locals())
    for ii in range(0, ngames):
      last = addToRow("score", "&nbsp;")
    last.attrs["class"] += " ui-corner-br"

  def renderBracket(bracketNumber, idPrefix, previousRowIndices = None):
    isCompressedFirstRound = compressFirstRound and bracketNumber == nbrackets
    if isCompressedFirstRound:
      nmatches = 1 << (bracketNumber - 2)
    else:
      nmatches = 1 << (bracketNumber - 1)
    column = 1+(nbrackets-bracketNumber)*colsPerBracket
    
    firstRound = (previousRowIndices is None)
    if firstRound:
      previousRowIndices = []
      for j in range(0, nmatches):
        pos = 3 + j * 6
        previousRowIndices.append(pos)
        previousRowIndices.append(pos)

    rowIndices = []          

    for i in range(0, 2*nmatches, 2):
      diff = previousRowIndices[i+1] - previousRowIndices[i]
      avg  = previousRowIndices[i] + diff / 2
      rowIndices.append(avg)
      if isCompressedFirstRound: 
        matchIndex = i+1
      else:
        matchIndex = i/2
      renderMatch(column, avg, bracketNumber-1, matchIndex, idPrefix)
      if firstRound:
        if compressFirstRound and not isCompressedFirstRound:
          table.addCell(bottomLink, column-2, avg+2)
          table.addCell(bottomLink, column-1, avg+2)
      else:
        table.addCell(topLink, column-2, previousRowIndices[i]+1)
        table.addCell(bottomLink, column-2, previousRowIndices[i+1]+2)
        link = SpanningCell(1, diff, '', {"class": "stretchlink"})
        table.addCell(link, column-2, previousRowIndices[i]+2)
        table.addCell(topLink,    column-1, avg+1)
        table.addCell(bottomLink, column-1, avg+2)

    return rowIndices

  previousRowIndices = None
  for i in range(nbrackets, 0, -1):
    previousRowIndices = renderBracket(i, tournamentId, previousRowIndices)
    if compressFirstRound and i == nbrackets:
      previousRowIndices = None

  # spacer calculation on last row:
  col = 1
  for i in range(nbrackets, 0, -1):
    if col > 1:
      table.addCell(SpanningCell(2, 1, '', {"class": "spacercalc"}), col, nrows-1) # links
      col += 2
    table.addCell(Cell('', {"class": "spacercalc"}), col, nrows-1) # seed
    col += 2
    table.addCell(SpanningCell(ngames, 1, '', {"class": "spacercalc"}), col, nrows-1) # links
    col += ngames  

  return table

def getCompetitions():
  dbh = DataBase()
#  comps = dbh.queryAndStore("select T.Id, T.Name, max(M.Match_Id) from Tournament T, TournamentMatch M where T.Year = 2014 and T.Id = M.Tournament_Id group by T.Id")
  comps = dbh.queryAndStore("select T.Id, T.Name, max(M.Round) from Tournament T, TournamentRound M where T.Year = 2014 and T.Id = M.Tournament_Id group by T.Id")
  
  def toDict(comp):
    # (id, name, maxId) = comp
    # nRounds = 1
    # while (maxId>>1) > 0:
    #   nRounds += 1
    #   maxId = (maxId>>1)
    # maxId = 1<<(nRounds-1)
    # nFirstMatches = dbh.queryAndStore("select count(*) from TournamentMatch where Tournament_Id = %s and Match_Id > %s", [id, maxId])[0][0]
    (id, name, nRounds) = comp
    return {"id": id, "name": name, "nRounds": nRounds, "compressesFirst": True}
  return [toDict(comp) for comp in comps]
                            

if __name__ == "__main__":

  comps = getCompetitions();
  comps_js = ", ".join(['{id: %(id)d, name: "%(name)s", nRounds: %(nRounds)d}' % row for row in comps])

  def generate_comp(comp):
    tname = comp["name"]
    tname = tname.replace("WSRC ", "").replace(" 2013", "").replace(" 2014", "")
    table = renderCompetition(comp["nRounds"], 5, comp["id"], comp["compressesFirst"])
    table.compress()
    html = etree.tostring(table.toHtml(), encoding='UTF-8', method='html')
    return {"id": comp["id"], "name": tname, "table": html}

  competitions = [generate_comp(comp) for comp in comps]
 
  templateDir = os.path.join(os.path.dirname(__file__), "jinja-templates")
  templateEnv = Environment(loader=FileSystemLoader(templateDir))
  template = templateEnv.get_template("body.html")
  kwargs = {"competitions_array": comps_js, "competitions": competitions}
  if os.getenv("USE_LOCALLINKS") is not None:
    kwargs["USE_LOCALLINKS"] = True
  print template.render(**kwargs).replace("&amp;nbsp;", "&nbsp;")


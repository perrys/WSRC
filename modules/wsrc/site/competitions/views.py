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

import rest_framework.filters
import rest_framework.views as rest_views
from django.shortcuts import get_object_or_404
import rest_framework.generics as rest_generics
import django.views.generic as view_generics
from django.template.response import TemplateResponse

from wsrc.site.usermodel.models import Player
from wsrc.site.competitions.models import Competition, CompetitionGroup, Match
from wsrc.site.competitions.serializers import PlayerSerializer, CompetitionSerializer, CompetitionGroupSerializer

# REST data views:

class PlayerList(rest_generics.ListAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

class PlayerDetail(rest_generics.RetrieveAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

class CompetitionList(rest_generics.ListAPIView):
    serializer_class = CompetitionSerializer
    filter_backends = [rest_framework.filters.OrderingFilter]
    ordering_fields = ("__all__")
    def get_queryset(self):
        queryset = Competition.objects.all()
        year = self.request.QUERY_PARAMS.get('year', None)
        if year is not None:
            queryset = queryset.filter(end_date__year=year)
        return queryset

class CompetitionDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = Competition.objects.all()
    serializer_class = CompetitionSerializer

class CompetitionGroupList(rest_generics.ListAPIView):
    model = CompetitionGroup

class CompetitionGroupDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = CompetitionGroup.objects.all()
    serializer_class = CompetitionGroupSerializer

class MatchDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    model = Match

class MatchCreate(rest_generics.CreateAPIView):
    model = Match

NON_BRK_SPACE = u'\xa0'

# HTML template views:

def boxes_view(request, group_id):
    """Return a view of the Leagues for identifier GROUP_ID. If
    GROUP_ID is zero or negative, the nth-previous League set is
    shown"""

    queryset = CompetitionGroup.objects
    offset = None 
    idx = int(group_id)
    if idx < 1:
        offset = - idx
    if offset is not None:        
        group = queryset.filter(comp_type="wsrc_boxes", active=True).order_by('-end_date')[offset]
    else:
        group = get_object_or_404(queryset, id=group_id)

    def create_box_config(previous_comp, competition, ctx):
        is_second = False
        ctx["maxplayers"] = max(ctx["maxplayers"], len(competition.players.all()))
        if previous_comp is not None:
            if previous_comp["name"][:-1] == competition.name[:-1]: # e.g. "League 1A" vs "League 1B"
                is_second = True
                previous_comp["colspec"] = 'double'
                previous_comp["nthcol"] = 'first'
        return {"colspec": is_second and "double" or "single",
                "nthcol": is_second and 'second' or 'first',
                "name": competition.name,
                "id": competition.id,
                "players": [p for p in competition.players.all()]
                }

    nullplayer = {"name": "", "id": ""}
    last = None
    boxes = []
    ctx = {"maxplayers": 0, "name": group.name, "id": group.id}
    for league in group.competitions.all():
        cfg = create_box_config(last, league, ctx)
        boxes.append(cfg)
        last = cfg
    for box in boxes:
        while len(box["players"]) < ctx["maxplayers"]:
            box["players"].append(nullplayer)
    ctx["boxes"] = boxes
    return TemplateResponse(request, "boxes.html", {"league_config": ctx, "disable_ajax_links": True})
    
    

def render_tournament(nbrackets, ngames, tournamentId, compressFirstRound):

    from wsrc.utils.html_table import Table, Cell, SpanningCell

    colsPerBracket = (4 + ngames)
    ncols = nbrackets * colsPerBracket - 1
    if compressFirstRound:
        nrows = 3 + (1 << nbrackets-2) * 6
    else:
        nrows = 3 + (1 << nbrackets-1) * 6
    table = Table(ncols, nrows, {"class": "bracket", "cellspacing": "0px"})

    topLink        = Cell('', {"class": "toplink"})
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
        table.addCell(SpanningCell(colsPerBracket-2, 1, content, {"class": "roundtitle"}, True),    1+0+(nbrackets-i)*colsPerBracket, 0)
        if i > 1:
            table.addCell(SpanningCell(1, 1, NON_BRK_SPACE, {"class": "leftspacer"}, True),    1 + colsPerBracket-2 + (nbrackets-i)*colsPerBracket, 0)
            table.addCell(SpanningCell(1, 1, NON_BRK_SPACE, {"class": "rightspacer"}, True), 1 + colsPerBracket-1 + (nbrackets-i)*colsPerBracket, 0)

    # first column; nbsp in the top row
    for i in range(1, nrows):
        content = NON_BRK_SPACE
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
            c = SpanningCell(1, 2, unicode(content), attrs)
            table.addCell(c, p.col, p.row)
            p.col += c.ncols
            return c
        addToRow("seed ui-corner-tl", NON_BRK_SPACE)
        addToRow("player", NON_BRK_SPACE, "match_%(idPrefix)s_%(binomialId)d_t" % locals())
        for ii in range(0, ngames):
            last = addToRow("score", NON_BRK_SPACE)
        last.attrs["class"] += " ui-corner-tr"

        p.col = col
        p.row += 2
        addToRow("seed ui-corner-bl", NON_BRK_SPACE)
        addToRow("player", NON_BRK_SPACE, "match_%(idPrefix)s_%(binomialId)d_b" % locals())
        for ii in range(0, ngames):
            last = addToRow("score", NON_BRK_SPACE)
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
            avg    = previousRowIndices[i] + diff / 2
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
                table.addCell(topLink,        column-1, avg+1)
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

def bracket_view(request, competition_id):
    import xml.etree.ElementTree as etree
    competition = get_object_or_404(Competition.objects, pk=competition_id)

    SETS_PER_MATCH=5

    def analyse(comp):
        # get the maximum match id
        try:
            maxId = reduce(max, [int(x.competition_match_id) for x in competition.match_set.all()], 0)
        except Exception, e:
            print 
            for c in competition.match_set.all().order_by("competition_match_id"):
                    print c.__dict__
            raise e
        nRounds = 1
        while (maxId>>1) > 0:
            nRounds += 1
            maxId = (maxId>>1)
        # figure out the number of matches in the first round. If it is equal or less than half of the possible slots 
        # then show the first round parallel with the second round
        maxSecondRoundId = (1<<(nRounds-1))-1
        firstRoundMatches = competition.match_set.filter(competition_match_id__gt=maxSecondRoundId)
        print firstRoundMatches
        nFirstMatches = len(firstRoundMatches)
        nSecondRoundMatches = (1 << (nRounds-2))
        return [nRounds, (nFirstMatches <= nSecondRoundMatches)]

    [nRounds, compressFirst] = analyse(competition)
    table = render_tournament(nRounds, SETS_PER_MATCH, competition.id, compressFirst)
    html = etree.tostring(table.toHtml(), encoding='UTF-8', method='html')
    
    return TemplateResponse(request, "tournaments.html", {"competition": competition, "bracket": html})
    

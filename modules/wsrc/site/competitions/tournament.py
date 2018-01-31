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

from wsrc.site.competitions.models import CompetitionGroup, Competition, Entrant, Match
from wsrc.utils.html_table import Table, Cell, SpanningCell
from django.db import transaction
from django.db.models import Q

import wsrc.utils.bracket
import lxml.etree as etree

NON_BRK_SPACE     = u'\xa0'

TOP_LINK          = Cell('', {"class": "toplink"})
BOTTOM_LINK       = Cell('', {"class": "bottomlink"})

SETS_PER_MATCH    = 5
COLS_PER_BRACKET  = 4 + SETS_PER_MATCH # + seeding, player/team name, and spacers

HEADER_ROWS       = 3
ROWS_PER_OPPONENT = 2 # we use rowspan=2 to allow "half" cell offsets
ROWS_PER_MATCH    = 3 * ROWS_PER_OPPONENT

def render_match(table, col, row, bracketIndex, matchIndex, idPrefix, match_map):

    binomialId = (1<<bracketIndex) + matchIndex
    attrs = dict(locals())
    match = match_map.get(binomialId)
    attrs["match_state"] = "empty_match"
    if match is not None:
        match.cache_scores()
        attrs["match_state"] = "partial-match" if match.is_unplayed() else "copleted-match"

    class Position:
        def __init__(self, col, row):
            self.row = row
            self.col = col

    cursor = Position(col, row)

    def get_match_content(key, is_top):
        if match is None:
            return NON_BRK_SPACE
        item = match
        team = "1" if is_top else "2"
        for tok in key.split("."):
            item = getattr(item, tok.format(team=team))
            if hasattr(item, "__call__"):
                item = item()
        return NON_BRK_SPACE if item is None else str(item)

    def addToRow(cls, key, is_top, cell_id=None):
        attrs = {"class": cls}
        content = get_match_content(key, is_top)
        if cell_id is not None:
            attrs["id"] = cell_id
        c = SpanningCell(1, ROWS_PER_OPPONENT, unicode(content), attrs)
        table.addCell(c, cursor.col, cursor.row)
        cursor.col += c.ncols
        return c

    def addOpponent(isTop):
        attrs["pos_identifier"] = isTop and 't' or 'b'
        addToRow("seed %(match_state)s ui-corner-%(pos_identifier)sl" % attrs, "team{team}.get_seed_or_handicap", isTop)
        prefix_class = ""
        team_id = None
        if match is not None and not match.is_unplayed():
            team_id = match.team1_id if isTop else match.team2_id
            if match.get_winner(key_only=True) == team_id:
                prefix_class = "winner "
        addToRow(prefix_class + "player %(match_state)s" % attrs, "team{team}.get_players_as_string", isTop,\
                 "match_%(idPrefix)s_%(binomialId)d_%(pos_identifier)s" % attrs)
        for ii in range(1, SETS_PER_MATCH+1):
            prefix_class = ""
            if team_id is not None and match.get_winner_of_set(ii, key_only=True) == team_id:
                prefix_class = "winningscore "
            last = addToRow(prefix_class + "score %(match_state)s" % attrs, "team{team}_score" + str(ii), isTop)
        last.attrs["class"] += " ui-corner-%(pos_identifier)sr" % attrs
#        last.content = str(binomialId)

    addOpponent(True)
    cursor.col = col
    cursor.row += ROWS_PER_OPPONENT
    addOpponent(False)



def render_bracket(table, nbrackets, bracketNumber, compressFirstRound, idPrefix, match_map, previousRowIndices = None):

    isFirstRound = (bracketNumber == nbrackets)
    isCompressedFirstRound = compressFirstRound and isFirstRound

    if isCompressedFirstRound:
        nmatches = 1 << (bracketNumber - 2)
    else:
        nmatches = 1 << (bracketNumber - 1)
    column = 1 + (nbrackets-bracketNumber) * COLS_PER_BRACKET

    if previousRowIndices is None:
        previousRowIndices = []
        for j in range(0, nmatches):
            pos = HEADER_ROWS + j * ROWS_PER_MATCH
            previousRowIndices.append(pos)
            previousRowIndices.append(pos)

    rowIndices = []

    for i in range(0, 2*nmatches, 2):
        diff = previousRowIndices[i+1] - previousRowIndices[i]
        avg  = previousRowIndices[i]   + diff / 2
        rowIndices.append(avg)
        if isCompressedFirstRound:
            matchIndex = i+1
        else:
            matchIndex = i/2
        render_match(table, column, avg, bracketNumber-1, matchIndex, idPrefix, match_map)
        if isFirstRound:
            if compressFirstRound and not isCompressedFirstRound:
                table.addCell(BOTTOM_LINK, column-2, avg+2)
                table.addCell(BOTTOM_LINK, column-1, avg+2)
        else:
            table.addCell(TOP_LINK, column-2, previousRowIndices[i]+1)
            table.addCell(BOTTOM_LINK, column-2, previousRowIndices[i+1]+2)
            link = SpanningCell(1, diff, '', {"class": "stretchlink"})
            table.addCell(link, column-2, previousRowIndices[i]+2)
            table.addCell(TOP_LINK,        column-1, avg+1)
            table.addCell(BOTTOM_LINK, column-1, avg+2)

    return rowIndices

def count_brackets(competition):
    # get the maximum match id
    try:
        maxId = reduce(max, [int(x.competition_match_id) for x in competition.match_set.all()], 0)
    except Exception, e:
        print
        for c in competition.match_set.all().order_by("competition_match_id"):
            print c.__dict__
        raise e
    return wsrc.utils.bracket.most_significant_bit(maxId)

def render_tournament(competition):
    """Generate an html table showing an empty bracket, sized for the given competition."""

    match_map = dict([(match.competition_match_id, match) for match in competition.match_set.all()])
    tournamentId = competition.id
    nbrackets = competition.nbrackets()

    # figure out the number of matches in the first round. If it is equal or less than half of the possible slots
    # then show the first round parallel with the second round
    maxSecondRoundId = (1<<(nbrackets-1))-1
    firstRoundMatches = competition.match_set.filter(competition_match_id__gt=maxSecondRoundId)
    nFirstMatches = len(firstRoundMatches)
    nSecondRoundMatches = (1 << (nbrackets-2))
    compressFirstRound = (nFirstMatches <= nSecondRoundMatches)

    rounds = dict([(r.round, r) for r in competition.rounds.all()])

    ncols = nbrackets * COLS_PER_BRACKET - 1
    if compressFirstRound:
        nrows = HEADER_ROWS + (1 << nbrackets-2) * ROWS_PER_MATCH
    else:
        nrows = HEADER_ROWS + (1 << nbrackets-1) * ROWS_PER_MATCH

    # Use our html table helper class to build up the html - allows us
    # to just fill in the (row,colum) cells we want and it will take
    # care of the blanks.
    table = Table(ncols, nrows, {"class": "bracket"})

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
        roundData = rounds.get(nbrackets-i+1)
        if roundData is not None:
            content += "\n[%s]" % roundData.end_date.strftime("%a %d %b")
        table.addCell(SpanningCell(COLS_PER_BRACKET-2, 1, content, {"class": "roundtitle"}, True),    1+0+(nbrackets-i)*COLS_PER_BRACKET, 0)
        if i > 1:
            table.addCell(SpanningCell(1, 1, NON_BRK_SPACE, {"class": "leftspacer"}, True),  1 + COLS_PER_BRACKET-2 + (nbrackets-i)*COLS_PER_BRACKET, 0)
            table.addCell(SpanningCell(1, 1, NON_BRK_SPACE, {"class": "rightspacer"}, True), 1 + COLS_PER_BRACKET-1 + (nbrackets-i)*COLS_PER_BRACKET, 0)

    # first column; nbsp in the top row
    for i in range(1, nrows):
        content = NON_BRK_SPACE
        if (i > 0):
            content = ""
        attribs = {'class': "verticalspacer"}
        if i == (nrows-1):
            attribs["class"] += " spacercalc"
        table.addCell(Cell(content, attribs), 0, i)

    # now draw the brackets
    previousRowIndices = None
    for i in range(nbrackets, 0, -1):
        previousRowIndices = render_bracket(table, nbrackets, i, compressFirstRound, tournamentId, match_map, previousRowIndices)
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
        table.addCell(SpanningCell(SETS_PER_MATCH, 1, '', {"class": "spacercalc"}), col, nrows-1) # links
        col += SETS_PER_MATCH

    return etree.tostring(table.toHtml(), encoding='UTF-8', method='html')

def get_current_competitions():
    tournament_group = CompetitionGroup.objects.filter(comp_type="wsrc_tournaments").get(active=True)
    comps = [c for c in tournament_group.competition_set.all()]
    tournament_groups = CompetitionGroup.objects.filter(comp_type="wsrc_qualifiers", active=True)
    for group in tournament_groups:
        comps.extend([c for c in group.competition_set.all()])
    return comps

def get_unplayed_matches(comp):
    def exclude_played_matches(queryset):
        predicate = (Q(team1_score1__isnull=True) | Q(team2_score1__isnull=True)) & Q(walkover__isnull=True)
        return queryset.filter(predicate)
    if comp.group.comp_type in ("wsrc_qualifiers", "wsrc_boxes"):
        unplayed_matches = []
        entrants = comp.entrant_set.all()
        nentrants = len(entrants)
        for i in range(0,nentrants):
            for j in range(i+1, nentrants):
                first_entrant = entrants[i]
                second_entrant = entrants[j]
                query = (
                  Q(team1=first_entrant,team2=second_entrant) |
                  Q(team2=first_entrant,team1=second_entrant)
                  )
                existing_matches = comp.match_set.filter(query)
                if existing_matches.count() > 0: # a match is already present in the DB
                    if existing_matches.count() > 1:
                        raise Exception("more than one match returned for competition {comp}, player1={p1}, player2={p2}".format(comp=comp.name, p1=first_entrant.player, p2=second_entrant.player))
                    if exclude_played_matches(existing_matches).count() > 0:
                        unplayed_matches.extend(existing_matches)
                else: # nothing in the DB
                    new_match = Match(competition=comp, team1=first_entrant, team2=second_entrant)
                    unplayed_matches.append(new_match)
    else:
        at_least_one_player_expr = Q(team1__isnull=False) | Q(team2__isnull=False)
        unplayed_matches = comp.match_set.filter(at_least_one_player_expr)
        unplayed_matches = exclude_played_matches(unplayed_matches)

    return unplayed_matches

def get_previous_match(match, team_number):
    previous_match_id = match.competition_match_id << 1
    if team_number == 2:
        previous_match_id += 1
    return Match.objects.filter(competition_id = match.competition_id).get(competition_match_id=previous_match_id)

def get_team_number(match, player_id):
    "Get the team number for this player in the given match"
    for team_number in [1,2]:
        team = match.get_team(team_number)
        if team is not None:
            for player in team.get_players():
                if player.id == player_id:
                    return team_number
    return None

def other_team_number(team_number):
    if team_number == 1:
        return 2
    return 1

def get_or_create_next_match(competition, slot_id, winning_team):
    is_bottomSlot = slot_id & 1
    match_id = slot_id >> 1
    try:
        match = competition.match_set.get(competition_match_id=match_id)
    except Match.DoesNotExist:
        match = competition.match_set.create(competition_match_id=match_id)
    if is_bottomSlot:
        match.team2 = winning_team
    else:
        match.team1 = winning_team
    match.save()
    return match

@transaction.atomic
def reset(comp_id, entrants):
    from serializers import EntrantDeSerializer
    competition = Competition.objects.get(pk=comp_id)
    for e in competition.entrant_set.all():
        e.delete()
    for m in competition.match_set.all():
        m.delete()
    for e in entrants:
        e["player1"] = e["player1"]["id"]
        e["player2"] = e.get("player2") and e["player2"]["id"] or None
        serializer = EntrantDeSerializer(data=e)
        if not serializer.is_valid():
            print serializer.errors
            raise Exception(serializer.errors)
        competition.entrant_set.add(serializer.save())
    entrants = competition.entrant_set.order_by("ordering")
    slots = wsrc.utils.bracket.calc_slots(len(entrants))
    for slot,entrant in zip(slots, entrants):
        get_or_create_next_match(competition, slot, entrant)

@transaction.atomic
def submit_match_winner(match, winning_team):
    match.save()
    get_or_create_next_match(match.competition, match.competition_match_id, winning_team)


@transaction.atomic
def set_rounds(comp_id, rounds):
    competition = Competition.objects.get(pk=comp_id)
    for r in competition.rounds.all():
        r.delete()
    for r in rounds:
        competition.rounds.create(**r)

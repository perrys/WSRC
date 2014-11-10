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

from django.http import HttpResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404
from django.http import Http404
from rest_framework.renderers import JSONRenderer
from wsrc.site.usermodel.models import Player
from wsrc.site.competitions.models import Competition

"""Views for the original tournament application, previously provided by a Flask server. Needed until it is fully migrated."""

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

@require_GET
def player_list(request):
    players = Player.objects.all()
    player_map = dict()
    for p in players:
        seeding = dict([(s.competition_id, s.seeding) for s in p.seeding.all()])
        player_details_map = {"name": p.get_full_name(), "shortname": p.get_short_name(), "seeding": seeding}
        player_map[p.id] = player_details_map
    return JSONResponse({"payload": player_map})


@require_GET
def competition_list(request):
    comps = Competition.objects.filter(end_date__year=2014) # TODO - query parameter as before?
    comp_map = dict()
    for c in comps:
        rounds = c.rounds.all()
        nRounds = len(rounds)
        comp_details_map = {"name": c.name, "nRounds": nRounds}
        comp_details_map["rounds"] = dict([(nRounds - r.round, r.end_date) for r in rounds])
        comp_map[c.id] = comp_details_map
    return JSONResponse({"payload": comp_map})

@require_GET
def match_list(request):
    competition_id = request.GET.get("id", None)
    if competition_id is None:
        raise Http404()
    competition_id = int(competition_id)
    comp = get_object_or_404(Competition.objects, id=competition_id)
    def match_dict(match):
        d = dict()
        for team in (1,2):
            for player in (1,2):
                k = "Team{team}_Player{player}_Id".format(**locals())
                d[k] = match.__dict__[k.lower()]
            for score in (1,2,3,4,5):
                k = "Team{team}_Score{score}".format(**locals())
                d[k] = match.__dict__[k.lower()]
        return d
    match_map = dict([(m.competition_match_id, match_dict(m)) for m in comp.match_set.all()])
    return JSONResponse({"payload": match_map})
    

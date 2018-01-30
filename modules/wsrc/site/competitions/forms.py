# -*- coding: utf-8 -*-
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

"Competition forms"

from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django import forms
from django.core.urlresolvers import reverse

from wsrc.utils.form_utils import make_readonly_widget, LabeledSelect, CachingModelChoiceField, add_formfield_attrs
from wsrc.site.competitions.models import Match, Entrant

# TODO - move admin forms here

class EntrantChoiceField(CachingModelChoiceField):
    def label_from_instance(self, entrant):
        return entrant.get_players_as_string()

class MatchScoresForm(forms.ModelForm):
    entrant_queryset = Entrant.objects.select_related("player1__user", "player2__user")
    team1 = EntrantChoiceField(queryset=entrant_queryset, label="Opponent 1")
    team2 = EntrantChoiceField(queryset=entrant_queryset, label="Opponent 2")

    class Meta:
        model = Match
        exclude = ["competition_match_id"]

    def __init__(self, *args, **kwargs):
        self.comp_id = kwargs.pop('comp_id', None)
        if self.comp_id is not None:
            self.comp_id = int(self.comp_id)
        mode = kwargs.pop('mode', None)
        super(MatchScoresForm, self).__init__(*args, **kwargs)
        self.fields['competition'].widget = forms.HiddenInput()
        self.fields['walkover'].label = "Walkover To"
        walkover_choices = Match.WALKOVER_RESULTS
        if "update" == mode:
            match = kwargs["instance"]
            walkover_choices = [(1, match.team1.get_players_as_string()),
                                (2, match.team2.get_players_as_string())]
            self.fields.pop('team1')
            self.fields.pop('team2')
        elif self.comp_id:
            entrant_queryset = self.entrant_queryset.filter(competition_id=self.comp_id)
            self.fields['team1'].queryset = entrant_queryset
            self.fields['team2'].queryset = entrant_queryset
        self.fields['walkover'].widget = forms.RadioSelect(choices=[('', '(None)')] + walkover_choices)
        choices = [(idx, idx) for idx in range(50,-1, -1)] + [("", "")]
        if False:
            choices = choices + [(idx, idx) for idx in range(-1,-51, -1)] # prefix this for handicaps
        for team in (1, 2):
            for aset in range(1, 6):
                self.fields["team{team}_score{aset}".format(**locals())].widget = forms.widgets.Select(choices=choices)
        add_formfield_attrs(self)

    def clean(self):
        if self.comp_id is not None and self.cleaned_data["competition"].pk != self.comp_id:
            raise ValidationError("Match has unexpected competition")
        return super(MatchScoresForm, self).clean()

    def add_error(self, field, error):
        if field is None:
            error = error.error_dict.get(NON_FIELD_ERRORS)
            if len(error) == 1:
                error = error[0]
                if hasattr(error, "code") and error.code == "match_exists":
                    match = error.params.get("match")
                    link = reverse('match_update', kwargs={"comp_id":match.competition_id, "pk":match.pk})
                    err_msg = "{msg} - follow this link to edit it: <a href='{link}' class='alert-link underline'>{match}</a>"\
                              .format(msg=error.message, link=link, match=match.get_teams_display().replace(" ", "&nbsp;"))
                    return super(MatchScoresForm, self).add_error(field, err_msg)
        return super(MatchScoresForm, self).add_error(field, error)
            
    

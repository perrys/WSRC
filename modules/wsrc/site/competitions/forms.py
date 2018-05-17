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
from django.urls import reverse
from django.db.models import Q

from wsrc.utils.form_utils import make_readonly_widget, LabeledSelect, CachingModelChoiceField, add_formfield_attrs
from wsrc.site.competitions.models import Match, Entrant

# TODO - move admin forms here

class EntrantChoiceField(CachingModelChoiceField):
    def label_from_instance(self, entrant):
        return entrant.get_players_as_string()

class MatchChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, match):
        return match.get_teams_display()

class MatchScoresForm(forms.ModelForm):
    entrant_queryset = Entrant.objects.select_related("player1__user", "player2__user")
    team1 = EntrantChoiceField(queryset=entrant_queryset, label="Opponent 1")
    team2 = EntrantChoiceField(queryset=entrant_queryset, label="Opponent 2")
    match = MatchChoiceField(queryset=Match.objects.none(), label="Match")

    class Meta:
        model = Match
        exclude = ["competition_match_id"]

    def __init__(self, *args, **kwargs):
        self.comp_id = kwargs.pop('comp_id', None)
        if self.comp_id is None:
            raise Exception("no competition ID supplied for match scores form")
        self.comp_id = int(self.comp_id)
        is_handicap = kwargs.pop('is_handicap', False)
        is_kiosk = kwargs.pop('is_kiosk', False)
        
        mode = kwargs.pop('mode', None)
        with_teams = kwargs.pop('with_teams', False)
        super(MatchScoresForm, self).__init__(*args, **kwargs)
        
        self.fields['competition'].widget = forms.HiddenInput()
        self.fields['walkover'].label = "Walkover To"
        walkover_choices = Match.WALKOVER_RESULTS

        tabindex = [1]
        def set_tab_index(field, resolve=True):
            if resolve:
                field = self.fields[field]
            field.widget.attrs["tabindex"] = tabindex[0]                
            tabindex[0] += 1

        set_tab_index("team1")
        set_tab_index("team2")
        set_tab_index("match")

        if "update" == mode:
            self.fields.pop("match")
            if not with_teams:
                self.fields.pop('team1')
                self.fields.pop('team2')
            match = kwargs["instance"]
            walkover_choices = [(1, match.team1.get_players_as_string()),
                                (2, match.team2.get_players_as_string())]
        elif "choose_and_update" == mode:
            self.fields.pop('team1')
            self.fields.pop('team2')
            match_queryset = Match.objects.select_related("team1__player1__user", "team1__player2__user",\
                                                          "team2__player1__user", "team2__player2__user")
            match_queryset = match_queryset.filter(competition_id=self.comp_id)
            match_queryset = match_queryset.filter(team1__isnull=False, team2__isnull=False)
            match_queryset = match_queryset.filter(Q(team1_score1__isnull=True) & Q(walkover__isnull=True))
            self.fields["match"].queryset = match_queryset
        else:
            self.fields.pop("match")
            entrant_queryset = self.entrant_queryset.filter(competition_id=self.comp_id)
            self.fields['team1'].queryset = entrant_queryset
            self.fields['team2'].queryset = entrant_queryset

        self.fields['walkover'].widget = forms.RadioSelect(choices=[('', '(None)')] + walkover_choices)

        score_choices = [("", "")] + [(idx, idx) for idx in range(0, 51, 1)]
        if is_handicap:
            score_choices = [(idx, idx) for idx in range(-50, 0, 1)] + score_choices# prefix this for handicaps

        for aset in range(1, 6):
            for team in (1, 2):
                field = self.fields["team{team}_score{aset}".format(**locals())]
                if not is_kiosk:
                    field.widget = forms.widgets.Select(choices=score_choices)
                field.widget.attrs["class"] = "score-input"
                set_tab_index(field, False)
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
            
    

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


from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.forms.fields import CharField
from django.forms import ModelForm
from django.forms.models import modelformset_factory
from django.forms.widgets import Select, CheckboxSelectMultiple, HiddenInput, Textarea

from wsrc.site.models import EventFilter
from wsrc.site.usermodel.models import Player

class SpaceTranslatingCharField(CharField):
    def to_python(self, value):
        value = super(SpaceTranslatingCharField, self).to_python(value)
        value = value.replace(" ", "_")
        return value

class SpaceTranslatingAuthenticationForm(AuthenticationForm):
    # allow spaces in usernames, which will be translated to underscores
    username = SpaceTranslatingCharField(max_length=254)


class SettingsUserForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(SettingsUserForm, self).__init__(*args, **kwargs)
        self.fields["first_name"].label = "First Name"
        self.fields["last_name"].label = "Last Name"
        self.fields["email"].label = "Email"
    class Meta:
        model = User
        fields = ["first_name", "last_name", "username",  "email"]

class SettingsPlayerForm(ModelForm):
    class Meta:
        model = Player
        fields = ["cell_phone", "other_phone", "short_name", "prefs_receive_email", "prefs_esra_member", "prefs_display_contact_details"]
        exclude = ('user',)
 
def create_notifier_filter_formset_factory(max_number):
    time_choices = [
        ("", "Please Select"),
        ("08:00:00", "8am"),
        ("10:00:00", "10am"),
        ("12:00:00", "12pm"),
        ("14:00:00", "2pm"),
        ("16:00:00", "4pm"),
        ("17:00:00", "5pm"),
        ("18:00:00", "6pm"),
        ("18:30:00", "6:30pm"),
        ("19:00:00", "7pm"),
        ("19:30:00", "7:30pm"),
        ("20:00:00", "8pm"),
        ("21:00:00", "9pm"),
        ("22:00:00", "10pm"),
                ]
    notice_period_choices = [
        ("", "Please Select"),
        (30, "30 minutes"),
        (60, "1 hour"),
        (120, "2 hours"),
        (180, "3 hours"),
        (240, "4 hours"),
        (300, "5 hours"),
        (360, "6 hours"),
        (720, "12 hours"),
        (1440, "1 day"),
        ]
    return modelformset_factory(
        EventFilter, 
        can_delete = True,
        extra=max_number,
        max_num=max_number,
        fields = ["earliest", "latest", "notice_period_minutes", "days", "player"],
        widgets = {
            "earliest": Select(choices=time_choices),
            "latest": Select(choices=time_choices),
            "notice_period_minutes": Select(choices=notice_period_choices),
            "days": CheckboxSelectMultiple(),
            "player": HiddenInput(),
        }
    )

class SettingsInfoForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(SettingsInfoForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            for field in ["cardnumber", "squashlevels_id", "wsrc_id", "booking_system_id"]:
                self.fields[field].widget.attrs['readonly'] = "readonly"
                self.fields[field].widget.attrs['disabled'] = "disabled"
            self.fields['membership_type'].widget.attrs['disabled'] = "disabled"
    
    class Meta:
        model = Player
        fields = ["membership_type",  "wsrc_id", "booking_system_id", "cardnumber",  "squashlevels_id"]
        exclude = ('user',)


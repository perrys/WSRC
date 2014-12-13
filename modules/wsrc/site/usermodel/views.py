from django.views.generic.list import ListView

from wsrc.site.usermodel.models import Player
from wsrc.site.competitions.views import get_competition_lists

class MemberListView(ListView):

    def get_queryset(self):
      return Player.objects.filter(user__is_active=True).order_by('user__first_name', 'user__last_name')

    def get_template_names(self):
      return ["memberlist.html"]

    def get_context_data(self, **kwargs):
        context = super(MemberListView, self).get_context_data(**kwargs)
        comp_lists = get_competition_lists()
        context.update(comp_lists)
        return context


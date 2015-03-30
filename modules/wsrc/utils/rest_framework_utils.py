
from rest_framework import serializers
from django.http import Http404


class LastUpdaterModelSerializer(serializers.ModelSerializer):
  """Specialized model serializer which updates a 'last_updated_by'
  field with the user from the request. The exact field name must be
  specified as the last_updater_field class field"""

  def __init__(self, *args, **kwargs):
    if "user" in kwargs:
      self.user = kwargs["user"]
      del kwargs["user"]
    elif "context" in kwargs:
      self.user = kwargs["context"]["request"].user
    super(LastUpdaterModelSerializer, self).__init__(*args, **kwargs)

  def update(self, instance, validated_data):
    self.set_last_updater(instance)
    return super(LastUpdaterModelSerializer, self).update(instance, validated_data)

  def create(self, validated_data):
    model_data = dict(validated_data)
    model_data[self.last_updater_field] = self.user
    return super(LastUpdaterModelSerializer, self).create(model_data)

  def set_last_updater(self, instance):
    if not self.user or not self.user.is_authenticated():
      raise Http404
    setattr(instance, self.last_updater_field, self.user)

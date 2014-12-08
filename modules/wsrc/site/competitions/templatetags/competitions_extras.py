from django.template import Library, Variable, VariableDoesNotExist

register = Library()

@register.filter
def as_range( value ):
  return range( value )

@register.filter
def escape_url( value ):
  return value.replace(" ", "_")

@register.assignment_tag()
def resolve(lookup, target):
    try:
        return lookup[target]
    except VariableDoesNotExist:
        return None


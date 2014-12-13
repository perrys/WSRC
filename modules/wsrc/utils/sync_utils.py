#!/usr/bin/python

import os.path
import unittest

from operator import itemgetter


class ModelRecordWrapper:
  """Wrap a DB record for dictionary access. Supports joins via dotted syntax - e.g. 'player.user'"""
  def __init__(self, record):
    self.record = record

  def __getitem__(self, name):
    record = self.record
    for tok in name.split("."):
      item = record = getattr(record, tok)
      if hasattr(item, "__call__"):
        item = item()
    return item

  @staticmethod
  def wrap_queryset(queryset):
    return [ModelRecordWrapper(record) for record in queryset.all()]

class FieldMappingWrapper:
  """Allow fields in a record to be accessed by alternative names"""
  def __init__(self, target, **field_mapping):
    self.target = target
    self.field_mapping = field_mapping

  def __getitem__(self, name):
    if name in self.field_mapping:
      name = self.field_mapping[name]
    return self.target[name]

  @staticmethod
  def wrap_records(records, **field_mapping):
    return [FieldMappingWrapper(r, **field_mapping) for r in records]
  
class FieldJoiningWrapper:
  """Create a new field by concatenating two existing fields. Useful for firstname + surname fields"""
  def __init__(self, target, field_name, join_fields, separator):
    self.target = target
    self.field_name = field_name
    self.join_fields = join_fields
    self.separator = separator

  def __getitem__(self, name):
    if name == self.field_name:
      return self.separator.join([self.target[f] for f in self.join_fields])
    return self.target[name]

  @staticmethod
  def wrap_records(records, field_name, join_fields, separator):
    return [FieldJoiningWrapper(r, field_name, join_fields, separator) for r in records]

class BooleanFieldWrapper:
  """Convert a yes/no field into a truth value"""
  def __init__(self, target, *fields):
    self.target = target
    self.fields = fields

  def __getitem__(self, name):
    val = self.target[name]
    if name in self.fields:
      return val is not None and val.lower()[0] == "y"
    return val

  @staticmethod
  def wrap_records(records, *fields):
    return [BooleanFieldWrapper(r, *fields) for r in records]
  
def parse_csv(filename):
  import csv
  fh = open(os.path.expanduser(filename))
  reader = csv.DictReader(fh)
  return [row for row in reader]

def report_differences(lhs, rhs, primary_key_field, data_fields):

  """Iterate over the two recordsets (which should be iterables of
  dictionary-like objects) returning records which have unique
  PRIMARY_KEY_FIELD values, and for common records return a dictionary
  of differences in DATA_FIELDS."""

  lhs_only = []
  rhs_only = []
  differences = {}

  lhs_iter = sorted(lhs, key=itemgetter(primary_key_field)).__iter__()
  rhs_iter = sorted(rhs, key=itemgetter(primary_key_field)).__iter__()

  def next_item(it, other_it, overflow_container, already_popped=None):
    try:
      item = it.next()
    except StopIteration, e:
      if already_popped is not None:
        overflow_container.append(already_popped)
      for i in other_it:
        overflow_container.append(i)
      raise e;
    return item;

  def compare(key, this, that):
    diff = {}
    for f in data_fields:      
      if this[f] != that[f]:
        diff[f] = (this[f], that[f])
    if len(diff) > 0:
      differences[key] = diff, this, that

  try:

    lhs_item = next_item(lhs_iter, rhs_iter, rhs_only)
    rhs_item = next_item(rhs_iter, lhs_iter, lhs_only)

    while True:

      lhs_key, rhs_key = [x[primary_key_field] for x in lhs_item, rhs_item]
    
      if lhs_key < rhs_key:
        lhs_only.append(lhs_item)
        lhs_item = next_item(lhs_iter, rhs_iter, rhs_only)
      elif lhs_key > rhs_key:
        rhs_only.append(rhs_item)
        rhs_item = next_item(rhs_iter, lhs_iter, lhs_only)
      else:
        compare(lhs_key, lhs_item, rhs_item)
        lhs_item = next_item(lhs_iter, rhs_iter, rhs_only)
        rhs_item = next_item(rhs_iter, lhs_iter, lhs_only, lhs_item)
    
  except StopIteration:
    pass

  return lhs_only, rhs_only, differences

class Tester(unittest.TestCase):
  
  def test_when_missing_elements_then_unique_elements_reported(self):

    def mk_list(l):
      return [{"id": x, "val": x} for x in l]

    # no difference
    lhs, rhs, diffs = report_differences(mk_list([1,2,3,4,5]), mk_list([1,2,3,4,5]), "id", ["val"])
    self.assertEqual(0, len(lhs))
    self.assertEqual(0, len(rhs))
    self.assertEqual(0, len(diffs))

    # middle missing
    lhs, rhs, diffs = report_differences(mk_list([1,2,4,5]), mk_list([1,2,3,4,5]), "id", ["val"])
    self.assertEqual(0, len(lhs))
    self.assertEqual(1, len(rhs))
    self.assertEqual(0, len(diffs))
    self.assertEqual({"id": 3, "val": 3}, rhs[0])

    # first missing
    lhs, rhs, diffs = report_differences(mk_list([2,3,4,5]), mk_list([1,2,3,4,5]), "id", ["val"])
    self.assertEqual(0, len(lhs))
    self.assertEqual(1, len(rhs))
    self.assertEqual(0, len(diffs))
    self.assertEqual({"id": 1, "val": 1}, rhs[0])
    
    # last missing
    lhs, rhs, diffs = report_differences(mk_list([1,2,3,4]), mk_list([1,2,3,4,5]), "id", ["val"])
    self.assertEqual(0, len(lhs))
    self.assertEqual(1, len(rhs))
    self.assertEqual(0, len(diffs))
    self.assertEqual({"id": 5, "val": 5}, rhs[0])

    # middle rhs missing
    lhs, rhs, diffs = report_differences(mk_list([1,2,3,4,5]), mk_list([1,2,4,5]), "id", ["val"])
    self.assertEqual(1, len(lhs))
    self.assertEqual(0, len(rhs))
    self.assertEqual(0, len(diffs))
    self.assertEqual({"id": 3, "val": 3}, lhs[0])

    # first missing
    lhs, rhs, diffs = report_differences(mk_list([1,2,3,4,5]), mk_list([2,3,4,5]), "id", ["val"])
    self.assertEqual(1, len(lhs))
    self.assertEqual(0, len(rhs))
    self.assertEqual(0, len(diffs))
    self.assertEqual({"id": 1, "val": 1}, lhs[0])
    
    # last missing
    lhs, rhs, diffs = report_differences(mk_list([1,2,3,4,5]), mk_list([1,2,3,4]), "id", ["val"])
    self.assertEqual(1, len(lhs))
    self.assertEqual(0, len(rhs))
    self.assertEqual(0, len(diffs))
    self.assertEqual({"id": 5, "val": 5}, lhs[0])

  def test_when_different_then_differences_reported(self):
    lhs = [
      {"id":1, "name": "Foo Bar", "widget": "Frobrinator"},
      {"id":2, "name": "Foo Baz", "widget": "Frobrinator"},
      ]
    rhs = [
      {"id":1, "name": "Foo Bar", "widget": "Frobrinator"},
      {"id":2, "name": "Foo Baz", "widget": "Forbrinator"},
      ]
    lhs, rhs, diffs = report_differences(lhs, rhs, "id", ["name", "widget"])
    self.assertEqual(0, len(lhs))
    self.assertEqual(0, len(rhs))
    self.assertEqual(1, len(diffs))
    
    self.assertIn(2, diffs)

    diff = diffs[2]
    self.assertIn("widget", diff)

    self.assertEqual({"widget": ("Frobrinator", "Forbrinator")}, diff)

if __name__ == '__main__':
    unittest.main()

#!/usr/bin/python

import sys
import json
import unittest

def _json_object_hook(dct):
  className = dct.get("cls")
  if className is not None:
    table = globals()
    for m in className.split("."):
      clazz = table[m]
      table = clazz.__dict__
    args = dct["args"]
    return clazz(**args)

  class AttributeDict(dict):
    def __getattr__(self, attr):
      return self[attr]
  return AttributeDict(**dct)

class TheJSONEncoder(json.JSONEncoder):
  # simple encoder will only work for classes with constructors with keywords which match their dictionary.
  default_types = [int, long, float, basestring, list, tuple, dict, bool, type(None)]
  def default(self, o):
    if type(o) in TheJSONEncoder.default_types:
      return JSONEncoder.default(self, o)
    if hasattr(o, "tojson"):
      return o.tojson()
    # TODO: test/fix this when __package__ is set
    return {"cls": o.__class__.__module__ + "." + o.__class__.__name__, "args": o.__dict__}


def deserializeFromString(s):
  return json.loads(s, object_hook = _json_object_hook)

def deserializeFromFile(fh):
  return json.load(fh, object_hook = _json_object_hook)

def serialize(obj):
  return json.dumps(obj, cls=TheJSONEncoder)

class Tester(unittest.TestCase):

  class TestClass:
    def __init__(self, arg1, arg2, arg3):
      self.arg1 = arg1
      self.arg2 = arg2
      self.arg3 = arg3

  def testSerializer(self):
    tc = Tester.TestClass("foo", "bar", "baz")
    s = serialize(tc)
    # Does not round-trip properly for inner classes
    self.assertEqual("""{"args": {"arg1": "foo", "arg2": "bar", "arg3": "baz"}, "cls": "__main__.TestClass"}""", s)

  def testDeserializeDict(self):
    s = '{"foo": "bar", "far": 23}'
    obj = deserializeFromString(s)
    self.assertEqual("bar", obj.foo)
    self.assertEqual(23, obj.far)

  def testDeserializeGeneric(self):
    def doDeserialize(cls, args):
      s = '{"cls": "%s", "args": {%s}}' % (cls, args)
      return deserializeFromString(s)

    filt = doDeserialize("Tester.TestClass", '"arg1": "foz", "arg2": "faz", "arg3": "fed"')
    self.assertIsInstance(filt, Tester.TestClass)
    self.assertEqual("foz", filt.arg1)


if __name__ == '__main__':
    unittest.main()

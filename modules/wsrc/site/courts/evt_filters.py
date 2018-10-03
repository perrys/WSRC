#!/usr/bin/python

import datetime
import unittest
from wsrc.utils.timezones import GBEireTimeZone

UK_TZINFO = GBEireTimeZone()

class IsFutureEvent:
  def __init__(self, delay=datetime.timedelta(hours=1), now=None):
    self.delay = delay
    self.now = now
  def __call__(self, evt):
    now = self.now
    if now is None: 
      now = datetime.datetime.now(UK_TZINFO)
    starttime = now + self.delay
    return evt.start_time > starttime

class IsPerson:
  def __init__(self, person):
    self.person = person
  def __call__(self, evt):
    return evt.name == self.person

class DaysOfWeek:
  def __init__(self, days):
    """DAYS is a list of day indices, where 1 is Monday and 7 is Sunday"""
    self.days = days
  def __call__(self, evt):
    return evt.start_time.isoweekday() in  self.days

class TimeOfDay:
  def __init__(self, starttime, endtime=datetime.time(23, 59, 59)):
    self.starttime = starttime
    self.endtime = endtime
  def __call__(self, evt):
    timeofday = evt.start_time.time()
    return timeofday >= self.starttime and timeofday <= self.endtime 

class And:
  def __init__(self, filters):
    self.filters = filters
  def __call__(self, evt):
    for f in self.filters:
      if not f(evt):
        return False
    return True

class Or:
  def __init__(self, filters):
    self.filters = filters
  def __call__(self, evt):
    for f in self.filters:
      if f(evt):
        return True
    return False

class Not:
  def __init__(self, filter):
    self.filter = filter
  def __call__(self, evt):
    return not self.filter(evt)

class Tester(unittest.TestCase):
  class TimeEvt:
    def __init__(self, d):
      self.start_time = d
  class PersonEvt:
    def __init__(self, p):
      self.name = p

  def testIsFuture(self):
    now = datetime.datetime.now()
    tester = IsFutureEvent(delay=datetime.timedelta(hours=2), now=now)
    mkevt = lambda h,m: Tester.TimeEvt(now + datetime.timedelta(hours=h, minutes=m))
    self.assertTrue (tester(mkevt(2, 1)))
    self.assertFalse(tester(mkevt(2, 0)))
    tester = IsFutureEvent(delay=datetime.timedelta(0), now=now)
    self.assertFalse(tester(mkevt(0, 0)))
    self.assertTrue (tester(mkevt(0, 1)))

  def testIsPerson(self):
    tester = IsPerson("Foo Bar")
    mkevt = lambda p: Tester.PersonEvt(p)
    self.assertTrue(tester(mkevt("Foo Bar")))
    self.assertFalse(tester(mkevt("Foo Baz")))

  def testTimeOfDay(self):
    evening = TimeOfDay(datetime.time(19, 0), datetime.time(22, 0))
    mkevt = lambda y,m,d,h,mi: Tester.TimeEvt(datetime.datetime(y,m,d,h,mi))
    self.assertTrue(evening(mkevt(2000, 1, 1, 20, 00)))
    self.assertTrue(evening(mkevt(2000, 1, 1, 19, 00)))
    self.assertFalse(evening(mkevt(2000, 1, 1, 23, 00)))
    self.assertFalse(evening(mkevt(2000, 1, 1, 22, 00)))
    
  def testDaysOfWeek(self):
    weekdayTest = DaysOfWeek([1,2,3,4,5])
    weekendTest = DaysOfWeek([6,7])
    mkevt = lambda y,m,d: Tester.TimeEvt(datetime.datetime(y,m,d))
    mon = mkevt(2014,10,13)
    fri = mkevt(2014,10,17)
    sat = mkevt(2014,10,18)
    sun = mkevt(2014,10,19)
    self.assertTrue(weekdayTest(mon))
    self.assertTrue(weekdayTest(fri))
    self.assertFalse(weekendTest(mon))
    self.assertFalse(weekendTest(fri))

    self.assertFalse(weekdayTest(sat))
    self.assertFalse(weekdayTest(sun))
    self.assertTrue(weekendTest(sat))
    self.assertTrue(weekendTest(sun))
    
  def testOr(self):
    t = lambda(x): True
    f = lambda(x): False
    self.assertTrue(Or([t])(None))
    self.assertTrue(Or([t, f])(None))
    self.assertTrue(Or([f, t])(None))
    self.assertTrue(Or([f, f, t])(None))
    self.assertFalse(Or([f])(None))
    self.assertFalse(Or([f, f])(None))

  def testAnd(self):
    t = lambda(x): True
    f = lambda(x): False
    self.assertTrue(And([t])(None))
    self.assertTrue(And([t, t])(None))
    self.assertFalse(And([f])(None))
    self.assertFalse(And([f, t])(None))
    self.assertFalse(And([t, f])(None))

  def testNot(self):
    t = lambda(x): True
    f = lambda(x): False
    self.assertTrue(Not(f)(None))
    self.assertFalse(Not(t)(None))

if __name__ == '__main__':
    unittest.main()
                      
    


import MySQLdb

def batchCursor(store, batchsize=512):
  while True:
    results = store.fetchmany(batchsize)
    if not results:
      break;
    for result in results:
      yield result

class DataBase:

  def __init__(self):
    self.dbh = MySQLdb.connect(user="user", db="legacy_squash", passwd="tLeWvrDRK3CeX4Kq")

  def queryAndStore(self, sql, params=None, wantFields = False):
    c = self.dbh.cursor()
    c.execute(sql, params)
    results = [row for row in batchCursor(c)]
    if wantFields:
      field_names = [i[0] for i in c.description]
      return results, field_names
    return results

  def update(self, sql, params=None):
    c = self.dbh.cursor()
#    print sql, params
    c.execute(sql, params)
    self.dbh.commit()

#!/opt/bin/python

import os.path
import xml.dom.minidom

def _getChildText(xml, name, required=True):
  elts = xml.getElementsByTagName(name)
  if len(elts) == 0:
    if required:
      raise Exception("schama violation - missing %(name)s tag" % locals())
    else:
      return None
  if len(elts) != 1:
    raise Exception("schama violation - require exactly 1 %(name)s tags" % locals())
  text = elts[0].firstChild
  if xml.TEXT_NODE != text.nodeType:
    raise Exception("schama violation - %(name)s must contain only text" % locals())
  return text.nodeValue


class SMTPConfig:
  def __init__(self, xml):
    def getChildText(name, required=True):
      return _getChildText(xml, name, required)

    self.server   = getChildText("Server")
    self.port     = int(getChildText("Port"))
    self.password = getChildText("Password")
    self.username = getChildText("Username")
    self.isSecure = getChildText("IsSecureConnection", False) is not None

class User:
  def __init__(self, xml):
    if not xml.hasAttribute("id"):
      raise Exception("schema violation - must supply id attribute")
    self.id = xml.getAttribute("id")
    
    def getChildText(name, required=True):
      return _getChildText(xml, name, required)

    self.displayname = getChildText("displayname")
    self.login = getChildText("login")
    self.password = getChildText("password")
    self.email = getChildText("email")
    self.ics_email = getChildText("ics_email", False)

class UserConfig:
  def __init__(self, xmlOrFileName):
    if isinstance(xmlOrFileName, str):
      filename = os.path.expanduser(xmlOrFileName)
      fh = open(filename, "r")
      fh.close()
      fh = open(filename, "r")
      doc = xml.dom.minidom.parse(fh)
    else:
      doc = xmlOrFileName
    users = [User(userXml) for userXml in doc.getElementsByTagName("user")]
    self.users = dict([(user.id, user) for user in users])

DEFAULT_FILENAME = "/var/services/homes/user/etc/users.xml"
DEFAULT_EMAIL_FILENAME = "/var/services/homes/user/etc/smtp.xml"

def getUsers(filename=None):
  if None == filename:
    filename = DEFAULT_FILENAME
  uconfig = UserConfig(filename)
  return uconfig.users

def getSMTPConfig(filename=None):
  if None == filename:
    filename = DEFAULT_EMAIL_FILENAME
  filename = os.path.expanduser(filename)
  fh = open(filename, "r")
  doc = xml.dom.minidom.parse(fh)
  fh.close()
  return SMTPConfig(doc)

def getConfigForUser(user, filename=None):
  users = getUsers(filename)
  if user in users:
    return users[user]
  raise Exception("user \"%(user)s\" not known" % locals())

if __name__ == "__main__":
  from pprint import pprint

  test_file = "~/dev/AutoBooker/etc/users.xml"

  u = UserConfig(test_file)
  pprint(u.users)

  u = getConfigForUser("bryantj", test_file)
  pprint(u.__dict__)

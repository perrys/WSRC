#!/opt/bin/python

import smtplib
import unittest
import traceback

TEST_MODE = False

def send(headers, body, config):

  if "From" not in headers:
    headers["From"] = config.username

  if "To" not in headers:
    raise Exception("cannot send email - no To: address supplied")

  message = "\n".join(["%(k)s: %(v)s" % locals() for k,v in headers.iteritems()])
  server = smtplib.SMTP(config.server, config.port)

  if config.isSecure:
    server.ehlo()
    server.starttls()
    server.ehlo()

  (retcode, response) = server.login(config.username, config.password)
  if retcode != 235:
    raise Exception("unable to log in to SMTP server, responsecode: %(retcode)d, message:\n\n%(response)s\n" % locals())

  message += "\n\n"
  message += body

  return server.sendmail(headers["From"], headers["To"], message)

def send_mixed_mail(sender, recipient, subject, textMsg, htmlMsg, config):
  boundary = "------=_NextPart_DC7E1BB5_1105_4DB3_BAE3_2A6208EB099D"
  headers = {"From": sender, 
             "To": recipient, 
             "Reply-to": "tournaments@wokingsquashclub.org", 
             "Subject": subject,
             "Content-type": "multipart/alternative; boundary=\"%(boundary)s\"" % locals()}

  msg = """--%(boundary)s
Content-type: text/plain; charset=iso-8859-1
""" % locals()
  msg += textMsg
  msg += """--%(boundary)s
Content-type: text/html; charset=iso-8859-1
""" % locals()
  msg += htmlMsg
  msg += "--%(boundary)s--" % locals()

  if True:
#  if recipient == "stewart.c.perry@gmail.com":
    try:
      if TEST_MODE:
        print headers
        print msg
      else:
        send(headers, msg, config)
        print "*successs* " + recipient 
    except Exception, e:
      print e
      traceback.print_exc()
      print headers
      print msg
      raise e

class tester(unittest.TestCase):
  def testEmailer(self):

    import jsonutils
    import os.path
    config = open(os.path.expanduser("../../etc/smtp.json"))
    config = jsonutils.deserializeFromFile(config)["gmail"]
    toAddress = "stewart.c.perry@gmail.com"
    headers = {"To": toAddress,
               "From": "foobar@dbsquash.org",
               "Subject": "testing testing",
               "MIME-Version": "1.0"}
    body = "test message"
    print send(headers, body, config)


if __name__ == "__main__":
  suite = unittest.TestLoader().loadTestsFromTestCase(tester)
  unittest.TextTestRunner(verbosity=2).run(suite)
  exit(0)




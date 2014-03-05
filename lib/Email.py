#!/opt/bin/python

import smtplib
import unittest
import Config

def sendmail(headers, body, config=None):
  if config is None:
    config = Config.getSMTPConfig()

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

class tester(unittest.TestCase):
  def testEmailer(self):

    toAddress = "stewart.c.perry@gmail.com"
    headers = {"To": toAddress,
               "From": "foobar@dbsquash.org",
               "Subject": "testing testing",
               "MIME-Version": "1.0"}
    body = "test message"
    print sendmail(headers, body)


if __name__ == "__main__":
  suite = unittest.TestLoader().loadTestsFromTestCase(tester)
  unittest.TextTestRunner(verbosity=2).run(suite)
  exit(0)




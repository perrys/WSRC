#!/usr/bin/env python

# This file is part of WSRC.
#
# WSRC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# WSRC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WSRC.  If not, see <http://www.gnu.org/licenses/>.

"""
Simple native messaging app to obtain wireless adapter information on Linux systems. 

To use, put this file in ~/bin/wireless.py, ensure that it is executable, and run the following:

mkdir -p ~/.config/chromium/NativeMessagingHosts
cat > ~/.config/chromium/NativeMessagingHosts/org.wokingsquashclub.chrome_app.wireless.json << EOF
{
  "name": "org.wokingsquashclub.chrome_app.wireless",
  "description": "Chrome Native Messaging API Example Host",
  "path": "$HOME/bin/wireless.py",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://aoapekckicdepaogkebkimagcpeffaih/",
    "chrome-extension://fadaddcjnkjhojpmnkgmlainjjejankf/"
  ]
}
EOF

For more information on the native messaging API, visit:

https://developer.chrome.com/extensions/nativeMessaging
"""

import json
import struct
import sys
import subprocess

WIRELESS_CMD = "iwconfig"


def get_wireless_data(if_name):
  args = [WIRELESS_CMD, if_name]
  proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  proc.wait()
  if proc.returncode != 0:
    for line in proc.stderr:
      sys.stderr.write(line)
    sys.exit(proc.returncode)
  result = dict()
  def getattrib(line, attrib, ntokens):
    if attrib in line:
      idx = line.find(attrib)
      if idx >= 0:
        keyval = line[idx:].split("=")
        val = keyval[1]
        val = " ".join(val.split()[:ntokens])
        attrib = attrib.lower().replace(" ", "_").replace("-", "_")
        result[attrib] = val.strip()
      
  for line in proc.stdout:
    if line.startswith(if_name):
      tokens = line.split("ESSID:")
      result['essid'] = tokens[1].strip()
      result['type'] = tokens[0].replace(if_name, "").strip()
    else:
      getattrib(line, "Bit Rate", 2)
      getattrib(line, "Tx-Power", 2)
      getattrib(line, "Link Quality", 1)
      getattrib(line, "Signal level", 2)

  lq = result.get("link_quality")
  if lq is not None:
    tokens = lq.split("/")
    pct = 100.0 * float(tokens[0])/float(tokens[1])
    result["link_quality"] = "{0:.0f}%".format(pct)
  return result

def read_message(stream):
  text_length_bytes = stream.read(4)
  # Unpack message length as 4 byte integer.
  text_length = struct.unpack('i', text_length_bytes)[0]
  # Read the text (JSON object) of the message.
  text = stream.read(text_length).decode('utf-8')
  return json.loads(text)

def write_message(stream, obj):
  payload = json.dumps(obj)
  stream.write(struct.pack('I', len(payload)))
  stream.write(payload)
  stream.flush()

def test_roundtrip():
  import StringIO
  buf = StringIO.StringIO()
  in_msg = {'interface': 'wlan0'}
  write_message(buf, in_msg)
  buf.seek(0)
  out_msg = read_message(buf)
  assert(in_msg == out_msg)
  
if __name__ == "__main__":
  input_msg = read_message(sys.stdin)
  interface_names = input_msg['interfaces']
  output_msg = dict([(name, get_wireless_data(name)) for name in interface_names])
  write_message(sys.stdout, output_msg)
  



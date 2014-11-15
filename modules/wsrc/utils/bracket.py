import unittest

def to_binary_string(i):
  """Return a string with the binary representation of the given integer""" 
  l = []
  while (i > 0):
    l.append(str(i & 1))
    i = i >> 1
  if len(l) == 0:
    return "0"
  l.reverse()
  return "".join(l)

def binary_to_gray(num):
  """Convert an unsigned binary number to reflected binary Gray code.""" 
  return (num >> 1) ^ num

def gray_to_binary(num):
  """Convert a reflected binary Gray code number to a binary number."""
  mask = num >> 1
  while mask != 0:
    num = num ^ mask;
    mask = mask >> 1
  return num;

class Tester(unittest.TestCase):
  def testRoundTrip(self):
    import random
    i = 0
    def test(i):
      gray = binary_to_gray(i)
      self.assertEqual(i, gray_to_binary(gray))
    test(0)
    test(1)
    while (i < 100):
      r = random.randint(2,2**20)
      test(r)
      i += 1

if __name__ == '__main__':
    unittest.main()

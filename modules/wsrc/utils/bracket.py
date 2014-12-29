import unittest
import math

"""
Helper functions for calculating single-elimination tournament rounds
(a.k.a. "brackets").

Match Numbering and Properties
------------------------------

A single-elimination tournament is a binary tree. It is convenient to
label the matches in the tournament as follows:

 Quarter     Semi     Final
  Finals    Finals

  match4-+
         |--match2-+
  match5-+         |
                   |--match1
  match6-+         |
         |--match3-+
  match7-+

There are some interesting properties relating to this--

If rounds are counted (zero-indexed) backwards from the final, then
the number of matches per round is

 matches_per_round = 1 * 2^N
                   = 1 << N

E.g. for the quarter final round, N=2, matches_per_round = 4.

To find the preceding matches of a given match, left-shift the number
to get the upper-left match, then add 1 to get the lower-left
match. E.g. the preceding matches of match2 are 2<<1 and (2<<1)+1,
matches 4 and 5 respectively.

To find the following match for a given match, right-shift the
number. E.g. the match following match 6 is

               6 >> 1
             = 110b >> 1
             = 11b
             = 3

In each match there is a top and bottom slot. The top slot comes from
the upper left previous match, and the bottom slot from the lower left
previous match. Thus we can number slots in each match as the number
of the match which determines the occupant of that slot. Converting
from match number to slot number, and vice-versa, follows the rules
for navigating left and right given above.

Seeding
-------

In many competitions, entrants are ranked (a.k.a. "seeded"), and the
tournament is arranged so that the top 2 seeds cannot meet until the
final, they cannot meet the 3rd or 4th seeds until the semi-finals,
and so on. For a tournament with 7 seeds, assuming all match results
follow the seeding predictions, this works out as follows:
                
 QuarterFinals          SemiFinals             Final
                
  seed1_vs_??    --+
                   |-- seed1_vs_seed4 --+
  seed4_vs_seed5 --+                    |
                                        |-- seed1_vs_seed2
  seed2_vs_seed7 --+                    |
                   |-- seed2_vs_seed3 --+
  seed3_vs_seed6 --+


We would like to find the mapping function from seed number to initial
match number and slot. Following our match naming convention, we
require:

 seed1 -> match4, slot0 (1000b)
 seed2 -> match6, slot0 (1100b)
 seed3 -> match7, slot0 (1110b)
 seed4 -> match5, slot0 (1010b)

 seed5 -> match5, slot1 (1011b)
 seed6 -> match7, slot1 (1111b)
 seed7 -> match6, slot1 (1101b)

It is clear that the slot numbers differ by one bit each time, which
arises from choosing the most significant path difference for the 1st
and 2nd seeds (which end up in different halves of the draw), then the
next most significant for the 3rd seed, which ends up in the other 
side of sub-tournament in the lower half of the draw, then switching
back to the upper half of the draw and putting the 4th seed in the
lower half of that, and so on.

A well-known example of this kind of pattern is the Gray code
(a.k.a. reflected binary code), in which subsequent entries always
differ by exactly 1 bit. The 3-bit Gray code is:

 Decimal  Binary  Gray
   0       000     000
   1       001     001
   2       010     011
   3       011     010
   4       100     110
   5       101     111
   6       110     101
   7       111     100


Comparing the seed->match mapping with the Gray code for zero-indexed
rankings (e.g. seed3 = zero_indexed_seed2 -> 011), the bits in this
code correspond to the branching decisions as we traverse the binary
tree from right-to-left. So seed3 should go in the lower half of the
draw (as bit1 = 1), and should go in the lower half of the lower draw
(because bit2 = 1), and should be the upper slot in that match (as
bit3 = 0). Following from this, if we reverse the bits in the 3-bit
Gray code for (seed_number -1), then we _almost_ get the slot index
(110b). We just need to OR this with 1000b to place the slot is in the
quarter final round.

Generalizing for arbitrary numbers of entrants, first consider the
situation where the number of entrants is exactly a power of 2:

  number_of_entrants = 2^n
                     = 1 << (n-1)

Then the slot index for each entrant is given by:

 slot_number = (1 << n) + bit_reverse(G_n(ranking-1))

where G_n() maps positive integers to their n-bit Gray codes. Note
that for compeitions where only a subset of the entrants are seeded,
the remaining entrants should be distributed randomly, so can simply
be assigned random seeds.

When the number of entrants is not an exact power of 2, then there
will be some entrants who do not participate in the first round--they
are given "byes". Byes are normally awarded to the highest-ranked
players, which means that the non-bye matches are "reflected" around
the nearest power of 2. For example, in a 10-player tournament, seed9
plays seed8 in the first round, seed10 plays seed7, and so on.

Following from this, in order to calculate the initial slots in this
situation, first calculate:

  n1 = floor(log2(num_entrants))
  n2 = ceil(log2(num_entrants))

Then find the number of entrants with seeding greater than n1:

  nearest = 1 << n1
  delta   = num_entrants - nearest
  cutoff  = nearest - delta
  
For seeds in the interval [1, cutoff] - apply the ranking-to-slot
algorithm with n1, and for the interval (cutoff, num_entrants] apply
it with n2.

"""

def to_binary_string(i):
  """Return a string with the binary representation of the given integer"""
  return "{:b}".format(i)

def binary_to_gray(num):
  """Convert an unsigned binary number to reflected binary Gray code."""
  return (num >> 1) ^ num

def gray_to_binary(num):
  """Convert a reflected binary Gray code number to an integer."""
  mask = num >> 1
  while mask != 0:
    num = num ^ mask;
    mask = mask >> 1
  return num;

def reverse(i, n):
  """Reverse the N-bit pattern of unsigned integer I. Returns the reversed integer."""
  r = 0
  count = 0
  if n < 1:
    raise Exception("unable to reverse bit patterns less than 1 wide!")
  while True:
    r |= i & 1
    i >>= 1
    count += 1
    if count == n:
      break
    r <<= 1
  return r

def calc_slots(num_entrants):
  """Return the initial slot positions for a single-elimination
  tournament with number of entrants NUM_ENTRANTS, in seed order""" 

  log2n = math.log(num_entrants, 2)
  n1 = int(log2n)
  n2 = int(math.ceil(log2n))
  nearest = 1 << n1
  delta   = num_entrants - nearest
  cutoff  = nearest - delta
  
  slots = []
  for r in range(1, num_entrants+1):
    gray = binary_to_gray(r-1)
    if (r <= cutoff):
      width = n1
    else:
      width = n2
    code = reverse(gray, width)
    code |= (1 << width)
#    print "rank: {0}, gray: {1:b}, slot: {2} ({2:b})".format(r, gray, code) 
    slots.append(code)
  return slots

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

  def testReverse(self):

    def test(bin_in, bin_out, width):
      r = reverse(int(bin_in, 2), width)
      self.assertEqual(int(bin_out, 2), r)

    test('0', '0', 1)
    test('1', '1', 1)
    test('01', '10', 2)
    test('10', '10', 3)
    test('10101', '10101', 5)
    test('1101', '1011', 4)
    test('100101', '101001', 6)

  def testRankingsToSlots(self):
    # simple power of 2 and ordered
    expected = [4,6,7,5]
    self.assertEqual(expected, calc_slots(len(expected)))

    # odd number of entrants (1 over nearest power of 2):
    expected = [4,6,7,10,11]
    self.assertEqual(expected, calc_slots(len(expected)))

    # even number of entrants (2 over nearest power of 2):
    expected = [4,6,14,10,11,15]
    self.assertEqual(expected, calc_slots(len(expected)))
    
    # 1 less than next power of 2:
    expected = [4,12,14,10,11,15,13]
    self.assertEqual(expected, calc_slots(len(expected)))


if __name__ == '__main__':
    unittest.main()

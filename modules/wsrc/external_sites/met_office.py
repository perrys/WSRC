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

import datetime
import json
import math
import operator
import pprint
import urllib, httplib
from django.utils import timezone

from collections import namedtuple

from wsrc.utils import url_utils
from wsrc.utils.timezones import UTC_TZINFO


WeightedPair = namedtuple("WeightedPair", ["value", "weight"])

OBSERVATION_FIELDS = (("temperature", "T"), ("dew_point", "Dp"), ("relative_humidity", "H"), ("pressure", "P"))
ObservationSet = namedtuple("ObservationSet", [o[0] for o in OBSERVATION_FIELDS])

class WeightedMean(object):
    def __init__(self, *value_weight_pairs):
        self.value_weight_pairs = value_weight_pairs
        self.total_weight = reduce(lambda x,y: x+y[1], self.value_weight_pairs, 0)
        
    def __float__(self):
        def red(x,y): return x + y[0] * y[1]
        return reduce(red, self.value_weight_pairs, 0) / self.total_weight

    def __repr__(self):
        return "{0:.2f} +/- {1:.2f}".format(float(self), self.std_dev)
#        return  repr(self.value_weight_pairs)

    @property
    def weighted_var(self):
        avg = float(self)
        sum_of_square_diffs = reduce(lambda x,y: x + (y[0]-avg)*(y[0]-avg)*y[1], self.value_weight_pairs, 0)
        return sum_of_square_diffs / self.total_weight
    
    @property
    def std_dev(self):
        return math.sqrt(self.weighted_var)

    
class MetOfficeObservations(object):

    def __init__(self, data, reference_point):
        self.data = data["SiteRep"]["DV"]["Location"]
        self.location = self.data["name"]
        point = (float(self.data["lat"]), float(self.data["lon"]))
        self.ref_point_distance = great_circle_distance(reference_point, point)
        self.time_to_observations_map = {}
        for data_point in self.data["Period"]:
            assert(data_point["type"] == "Day")
            date = datetime.datetime.strptime(data_point["value"], "%Y-%m-%dZ")
            date = date.replace(tzinfo=UTC_TZINFO)
            obs_list = data_point["Rep"]
            if isinstance(obs_list, dict):
                obs_list = (obs_list,)
            for obs in obs_list:
                mins = int(obs["$"])
                obs_time = date + datetime.timedelta(minutes=mins)
                observation = ObservationSet(*[obs[o[1]] for o in OBSERVATION_FIELDS])
                self.time_to_observations_map[obs_time] = observation
    
class MetOfficeSession(object):

    DATAPOINT_SERVER = "http://datapoint.metoffice.gov.uk"
    OBSERVATIONS_ENDPOINT_PREFIX = "/public/data/val/wxobs/all/json"

    def __init__(self):
        from wsrc.site.models import OAuthAccess
        self.oauth_record = OAuthAccess.objects.get(name="Met Office")

    def get_sitelist(self):
        return self.get_observation_data("/sitelist", {"res": "hourly"})
    
    def get_observation_data(self, location, params=None):
        params = dict(params) if params is not None else {"res": "hourly"}
        params.update({"key": self.oauth_record.client_secret})
        selector = self.OBSERVATIONS_ENDPOINT_PREFIX + "/" + location
        selector += "?" + urllib.urlencode(params)        
        return self.api_request(self.DATAPOINT_SERVER, selector)

    @classmethod
    def augment_location_with_distance(cls, loc, reference_point):
        loc["distance"] = great_circle_distance(reference_point, (float(loc["latitude"]), float(loc["longitude"])))
        
    def get_locations_sorted_by_distance(self, point_a):
        sites = self.get_sitelist()
        locations = sites["Locations"]["Location"]
        for l in locations:
            self.augment_location_with_distance(l, point_a)
        locations.sort(key=operator.itemgetter("distance"))
        return locations

    @classmethod
    def api_request(cls, server, endpoint, method="GET", body=None):
        headers = {
            "user-agent": "wsrc_club_agent",
            "Accept": "application/json",
        }
        headers, data = url_utils.request(server + endpoint, method, headers=headers, body=body)
        if headers.status >= httplib.BAD_REQUEST:
            if "json" in headers.get("content-type"):
                data = json.loads(data)
                raise APIException(data["title"], data["detail"], data["type"])
        elif headers.status == httplib.NO_CONTENT:
            return None
        return json.loads(data)

def get_distance_weigted_average_observations(reference_point, *locations, **kwargs):
    session_factory=kwargs.get("session_factory", lambda: MetOfficeSession())
    date_filter=kwargs.get("date_filter", lambda x: True)
    session = session_factory()    
    location_observation_sets = [MetOfficeObservations(session.get_observation_data(l), reference_point) for l in locations]
    datetimes = None
    for obs_set in location_observation_sets:
        these_dates = set(obs_set.time_to_observations_map.keys())
        if datetimes is None:
            datetimes = these_dates
        else:
            datetimes.intersection_update(these_dates)
    results = dict()
    for datetime in datetimes:
        if date_filter(datetime):
            field_values = []
            for field, code in OBSERVATION_FIELDS:
                value_weight_pairs = []
                for observation_set in location_observation_sets:
                    observations = observation_set.time_to_observations_map[datetime]
                    weight = 1.0 / observation_set.ref_point_distance
                    value_weight_pairs.append((float(getattr(observations, field)), weight))
                field_values.append(WeightedMean(*value_weight_pairs))
            avg_observation_set = ObservationSet(*field_values)
            results[datetime] = avg_observation_set
    return results

def fetch_and_store_distance_weigted_average_observations(reference_point, *locations):
    from wsrc.site.courts.models import HumidityMeasurement
    now = timezone.now()
    location = "Outside"
    recent_observations = HumidityMeasurement.objects.filter(location=location, time__gt=(now-datetime.timedelta(days=2)))
    obs_times = [obs.time for obs in recent_observations]
    date_filter = lambda x: x not in obs_times
    new_observations = get_distance_weigted_average_observations(reference_point, *locations, date_filter=date_filter)
    for time, obs in new_observations.iteritems():
        kwargs = {}
        for field in OBSERVATION_FIELDS:
            field = field[0]
            weighted_avg = getattr(obs, field)
            kwargs[field] = float(weighted_avg)
            kwargs[field + "_error"] = weighted_avg.std_dev
        model = HumidityMeasurement(location=location, time=time, **kwargs)
        model.save()
    
def great_circle_distance(point_a, point_b):
    "Calculate as-the-crow-flys distance between two coordinates"

    def to_radians(a):
        return a/180.0 * math.pi
    lat1, lon1 = [to_radians(x) for x in point_a]
    lat2, lon2 = [to_radians(x) for x in point_b]
    
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = math.sin(delta_lat/2) * math.sin(delta_lat/2) + \
        math.cos(lat1) * math.cos(lat2) * \
        math.sin(delta_lon/2) * math.sin(delta_lon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    R = 6371 # km
    return R * c
                                                             

if __name__ == "__main__":
    import wsrc.external_sites # call __init__.py
    import unittest

    class Tester(unittest.TestCase):

        @unittest.skip("no server dependency")
        def test_GIVEN_met_office_session_WHEN_retrieving_sitelist_THEN_something_returned(self):
            session = MetOfficeSession()
            sites = session.get_sitelist()
            self.assertIn("Locations", sites)
            locations = sites["Locations"]["Location"]
            self.assertGreater(len(locations), 0)

        def test_GIVEN_nearby_coordinates_WHEN_calculating_distance_THEN_approximate_distance_returned(self):
            location = (51.279, -0.772) # Farnborough, about 14km from CLUB_LOCATION
            CLUB_LOCATION = (51.3191298,-0.5716241)
            distance = great_circle_distance(CLUB_LOCATION, location)
            self.assertGreater(distance, 10)
            self.assertLess(distance, 20)

        def test_GIVEN_single_weighted_observation_WHEN_calculating_std_dev_THEN_zero_returned(self):
            obs = [WeightedPair(1.0, 400)]
            mean = WeightedMean(*obs)
            self.assertEqual(obs[0].value, float(mean))
            self.assertEqual(0.0, mean.std_dev)

        def test_GIVEN_equal_weighted_observations_WHEN_calculating_std_dev_THEN_std_dev_returned(self):
            obs = [WeightedPair(1.0, 400), WeightedPair(3.0, 400)]
            mean = WeightedMean(*obs)
            self.assertEqual(2.0, float(mean))
            self.assertEqual(1.0, mean.weighted_var)
            self.assertEqual(1.0, mean.std_dev)
            
            obs = [WeightedPair(1.0, 400), WeightedPair(2.0, 400), WeightedPair(3.0, 400)]
            mean = WeightedMean(*obs)
            self.assertEqual(2.0, float(mean))
            self.assertAlmostEqual(2.0/3, mean.weighted_var)
            self.assertAlmostEqual(math.sqrt(2.0/3), mean.std_dev)
            
        def test_GIVEN_unequal_weighted_observations_WHEN_calculating_std_dev_THEN_std_dev_returned(self):
            obs = [WeightedPair(1.0, 1), WeightedPair(5.0, 3)]
            mean = WeightedMean(*obs)
            self.assertEqual(4.0, float(mean))
            self.assertAlmostEqual(3.0, mean.weighted_var)
            self.assertAlmostEqual(math.sqrt(3), mean.std_dev)

        def test_GIVEN_raw_data_WHEN_creating_observation_set_THEN_consistent_data_returned(self):
            data = self._make_loc("foo", 51.3, -0.57, "2018-01-01Z", [
                (0, ObservationSet(20, 1020, 40, 50)), (1, ObservationSet(20, 1020, 40, 50))])
            observation_set = MetOfficeObservations(data, (51.5, 0)) # Greenwich
            self.assertEqual("foo", observation_set.location)
            self.assertAlmostEqual(45, observation_set.ref_point_distance, 0)
            self.assertEqual(2, len(observation_set.time_to_observations_map))
            dates = list(observation_set.time_to_observations_map.keys())
            dates.sort()
            self.assertEqual(datetime.datetime(2018, 1, 1, 1, tzinfo=UTC_TZINFO), dates[-1])
            
        def test_GIVEN_two_observation_sets_WHEN_combining_THEN_weighted_avg_data_returned(self):
            obs_sets = {"data1": self._make_loc("foo", 1, 0, "2018-01-01Z", [
                (0, ObservationSet(20, 40, 50, 1020)), (1, ObservationSet(16.7, 15.3, 91.4, 1013))]),
                        "data2": self._make_loc("bar", 2, 0, "2018-01-01Z", [
                            (0, ObservationSet(20, 40, 50, 1020)), (1, ObservationSet(17.9, 14.7, 81.4, 1013)), (2, ObservationSet(0, 0, 0, 0))])}
            def session_factory():
                class c:
                    def get_observation_data(self, loc):
                        return obs_sets[loc]
                return c()
            reference_point = (0, 0)
            avgs = get_distance_weigted_average_observations(reference_point, session_factory=session_factory, *["data1", "data2"])
            self.assertEqual(2, len(avgs))
            times = avgs.keys()
            times.sort()
            avg0 = avgs[times[0]]
            for mwa in avg0:
                self.assertAlmostEqual(0, mwa.std_dev)
            avg1 = avgs[times[1]]
            self.assertAlmostEqual(17.1, float(avg1.temperature), 1)
            self.assertAlmostEqual(0.6, avg1.temperature.std_dev, 1)
            self.assertAlmostEqual(88.1, float(avg1.relative_humidity), 1)
            self.assertAlmostEqual(4.7, avg1.relative_humidity.std_dev, 1)

            
        def _make_loc(self, name, lat, lon, date, timed_data):
            def mk_time(hour, obs):
                return {"T": str(obs.temperature), "P": str(obs.pressure), "Dp": str(obs.dew_point),
                        "H": str(obs.relative_humidity), "$": str(60 * hour)}
            times = {"type": "Day", "value": date, "Rep": [mk_time(*td) for td in timed_data]}
            data = {"SiteRep": {"DV": {"Location": {"lat": lat, "lon": lon, "name": name, "Period": [times]}}}}
            return data

    unittest.main()

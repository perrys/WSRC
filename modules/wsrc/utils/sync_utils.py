#!/usr/bin/python

import os.path
import unittest

from operator import itemgetter


def dotted_lookup(record, name):
    for tok in name.split("."):
        item = record = getattr(record, tok)
        if hasattr(item, "__call__"):
            item = record = item()
    return item

class ModelRecordWrapper(object):
    """Wrap a DB record for dictionary access. Supports joins via dotted syntax - e.g. 'player.user'"""
    def __init__(self, record):
        self.record = record

    def __getitem__(self, name):
        return dotted_lookup(self.record, name)

    @classmethod
    def wrap_records(cls, records):
        return [cls(record) for record in records]

class DisplayValueWrapper(ModelRecordWrapper):
    def __init__(self, record, fields):
        super(DisplayValueWrapper, self).__init__(record)
        self.fields = fields

    def __getitem__(self, name):
        if name in self.fields:
            return getattr(self.record, "get_{0}_display".format(name))()
        return super(DisplayValueWrapper, self).__getitem__(name)

    @classmethod
    def wrap_records(cls, records, *fields, **kwargs):
        return [cls(r, *fields, **kwargs) for r in records]


class NullifingWrapper:
    """Return null if field is empty string"""
    def __init__(self, target, *fields):
        self.target = target
        self.fields = fields

    def __getitem__(self, name):
        val = self.target[name]
        if name in self.fields and val == '':
            return None
        return val

    def __setitem__(self, name, val):
        self.target[name] = val

    @classmethod
    def wrap_records(cls, records, *fields):
        return [NullifingWrapper(r, *fields) for r in records]

class BooleanFieldWrapper:
    """Convert a yes/no field into a truth value"""
    def __init__(self, target, *fields):
        self.target = target
        self.fields = fields

    def __getitem__(self, name):
        val = self.target[name]
        if name in self.fields:
            if val is None or len(val) == 0:
                return None
            return val.lower()[0] == "y"
        return val

    def __setitem__(self, name, val):
        self.target[name] = val

    @classmethod
    def wrap_records(cls, records, *fields):
        return [cls(r, *fields) for r in records]

class IntegerFieldWrapper:
    """Return fields names with spaces when asked with underscores"""
    def __init__(self, target, *fields):
        self.target = target
        self.fields = fields

    def __getitem__(self, name):
        val = self.target[name]
        if name in self.fields and val is not None:
            if isinstance(val, float) or len(val) > 0:
                try:
                    return int(val)
                except ValueError:
                    pass
            return None
        return val

    def __setitem__(self, name, val):
        self.target[name] = val

    @classmethod
    def wrap_records(cls, records, *fields):
        return [cls(r, *fields) for r in records]

class DateFieldWrapper:
    def __init__(self, target, *fields):
        self.target = target
        self.fields = fields

    def __getitem__(self, name):
        val = self.target[name]
        if name in self.fields and val is not None:
            if isinstance(val, str) or isinstance(val, unicode):
                return val[:10]
            if hasattr(val, "date"):
                val = val.date()
        return val

    def __setitem__(self, name, val):
        self.target[name] = val

    @classmethod
    def wrap_records(cls, records, *fields):
        return [cls(r, *fields) for r in records]

class LowerCaseFieldWrapper:
    """Return lower-cased values"""
    def __init__(self, target, *fields):
        self.target = target
        self.fields = fields

    def __getitem__(self, name):
        val = self.target[name]
        if name in self.fields and val is not None:
            return val.lower()
        return val

    def __setitem__(self, name, val):
        self.target[name] = val

    @classmethod
    def wrap_records(cls, records, *fields):
        return [cls(r, *fields) for r in records]

def parse_csv(filename):
    import csv
    fh = open(os.path.expanduser(filename))
    reader = csv.DictReader(fh)
    return [row for row in reader]

def find_matching(lhs_records, rhs_records, comparer):
    """Find rows in RHS_RECORDS which match those in LHS_RECORDS. Returns
       an array of length len(LHS_RECORDS) with each element containing
       the corresponding row from RHS_RECORDS if a match is found, or
       None otherwise. Note that the first matching row is always
       recorded, and rows will not match more than once.
    """
    rhs_copy = list(rhs_records)
    result = list()
    for lhs in lhs_records:
        matched = None
        for i, rhs in enumerate(rhs_copy):
            if rhs is None:
                continue
            if comparer(lhs, rhs):
                matched = rhs
                rhs_copy[i] = None
                break
        result.append(matched)
    return result

def get_differences(rows, db_rows, matcher, differ):
    mapping_array = find_matching(rows, db_rows, matcher)
    differences = {}
    for i, db_row in enumerate(mapping_array):
        if db_row is not None:
            other_row = rows[i]
            other_row["db_id"] = db_row["id"]
            diffs = differ(other_row, db_row)
            if len(diffs) > 0:
                differences[db_row["id"]] = diffs

    return differences

def match_spreadsheet_with_db_record(ss_row, db_record):
    def nontrivial_equals(lhs, rhs):
        return lhs is not None and lhs == rhs
    if nontrivial_equals(ss_row["index"], db_record["wsrc_id"]):
        return True
    if nontrivial_equals(ss_row["cardnumber"], db_record["get_cardnumbers"]) and db_record["get_cardnumbers"] != "":
        return True
    if nontrivial_equals(ss_row["surname"], db_record["user.last_name"]) and nontrivial_equals(ss_row["firstname"], db_record["user.first_name"]):
        return True
    return False

def match_booking_system_contact_with_db_record(bs_row, db_record):
    def nontrivial_equals(lhs, rhs):
        return lhs is not None and lhs == rhs
    if nontrivial_equals(bs_row["id"], db_record["booking_system_id"]):
        return True
    return bs_row["name"] == u"{0} {1}".format(db_record["user.first_name"], db_record["user.last_name"])

def split_first_and_last_names(name):
    tokens = name.split(" ")
    firstnames = []
    surnames = []
    for i,tok in enumerate(tokens):
        if i==0:
            firstnames.append(tok)
        elif i==1 and len(tok) == 1:
            firstnames.append(tok) # first initial
        else:
            surnames.append(tok)
    return (" ".join(firstnames), " ".join(surnames))

class ComparisonSpec:
    def __init__(self, lhs_col, rhs_col):
        self.lhs_col = lhs_col
        self.rhs_col = rhs_col
    def __call__(self, lhs, rhs):
        lhs_val = lhs[self.lhs_col]
        rhs_val = rhs[self.rhs_col]
        if not lhs_val == rhs_val:
            return (lhs_val, rhs_val)
        return None
    def key(self):
        return self.rhs_col


def compare_booking_system_contact_with_db_record(bs_contact, db_record):
    diffs = dict()
    specs = [
        ComparisonSpec('last_name', 'user.last_name'),
        ComparisonSpec('first_name', 'user.first_name'),
        ComparisonSpec('email', 'user.email'),
        ComparisonSpec('id', 'booking_system_id'),
    ]
    for spec in specs:
        diff = spec(bs_contact, db_record)
        if diff is not None:
            diffs[spec.key()] = diff
    return diffs

def compare_spreadsheet_with_db_record(ss_row, db_record):
    diffs = dict()
    specs = [
        ComparisonSpec('active', 'user.is_active'),
        ComparisonSpec('surname', 'user.last_name'),
        ComparisonSpec('firstname', 'user.first_name'),
        ComparisonSpec('email', 'user.email'),
        ComparisonSpec('joiningdate', 'user.date_joined'),
        ComparisonSpec('birthdate', 'date_of_birth'),
        ComparisonSpec('Data Prot email', 'prefs_receive_email'),
        ComparisonSpec('index', 'wsrc_id'),
        ComparisonSpec('cardnumber', 'get_cardnumbers'),
        ComparisonSpec('mobile_phone', 'cell_phone'),
        ComparisonSpec('home_phone', 'other_phone'),
    ]
    for spec in specs:
        diff = spec(ss_row, db_record)
        if diff is not None:
            diffs[spec.key()] = diff
    return diffs

def get_differences_ss_vs_db(ss_records, db_records):
    from wsrc.site.usermodel.models import Player

    ss_records = BooleanFieldWrapper.wrap_records(ss_records, "active")
    ss_records = BooleanFieldWrapper.wrap_records(ss_records, "Data Prot email")
    ss_records = IntegerFieldWrapper.wrap_records(ss_records, "cardnumber", "index")
    ss_records = LowerCaseFieldWrapper.wrap_records(ss_records, "category")
    ss_records = DateFieldWrapper.wrap_records(ss_records, "joiningdate")
    ss_records = DateFieldWrapper.wrap_records(ss_records, "birthdate")
    ss_records = NullifingWrapper.wrap_records(ss_records, "surname", "firstname", "email", "mobile_phone", "home_phone")

    db_records = ModelRecordWrapper.wrap_records(db_records)
    db_records = DateFieldWrapper.wrap_records(db_records, "user.date_joined")
    db_records = DateFieldWrapper.wrap_records(db_records, "date_of_birth")
    db_records = NullifingWrapper.wrap_records(db_records, "user.last_name", "user.first_name", "user.email", "cell_phone", "other_phone")

    return get_differences(ss_records, db_records, match_spreadsheet_with_db_record, compare_spreadsheet_with_db_record)

def get_differences_bs_vs_db(bs_records, db_records):
    from wsrc.site.usermodel.models import Player

    db_records = ModelRecordWrapper.wrap_records(db_records)
    db_records = NullifingWrapper.wrap_records(db_records, "user.last_name", "user.first_name", "user.email")

    bs_records = NullifingWrapper.wrap_records(bs_records, "last_name", "first_name", "email")
    bs_records = IntegerFieldWrapper.wrap_records(bs_records, "id")

    return get_differences(bs_records, db_records, match_booking_system_contact_with_db_record, compare_booking_system_contact_with_db_record)

class Tester(unittest.TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        from wsrc.site.usermodel.models import Player
        try:
            user_instance = User.objects.get(username="xxx_test")
            user_instance.delete()
        except User.DoesNotExist:
            pass
        user_instance = User.objects.create_user("xxx_test", "xxx@xxx.xxx", "xxx_pw", first_name="Foo", last_name="Bar")
        user_instance.save()
        self.player_instance = Player.objects.create(cell_phone="07890 123456", other_phone="01234 567890",
                                                     wsrc_id=123456, prefs_receive_email=True, user=user_instance)
        self.player_instance.save()
        self.ss_record = {
            "active": "Y",
            "surname": "Foo",
            "firstname": "Bar",
            "category": "full",
            "email": "foo@bar.com",
            "Data Prot email": "Yes",
            "index": 123456,
            "mobile_phone": "07890 123456",
            "home_phone": "01234 567890",
        }
        self.bs_record = {"Email address": "foo@bar.baz", "Mobile": "07890 123456", "Telephone": "01234 567890", "Name": "Foo Bar"}

    def tearDown(self):
        self.player_instance.delete()

    def common_ss_test(self, field, val, record, expected):
        self.ss_record[field] = val
        self.assertEqual(expected, record[field])

    def common_db_test(self, field, record, expected):
        self.assertEqual(expected, record[field])

    def test_GIVEN_numeric_string_WHEN_integer_wraped_THEN_number_returned(self):
        record = IntegerFieldWrapper(self.ss_record, "cardnumber", "index")
        self.common_ss_test("index", "123", record, 123)
        self.common_ss_test("index", "", record, None)
        self.common_ss_test("index", None, record, None)

    def test_GIVEN_mixed_string_WHEN_lowercase_wraped_THEN_lowercase_string_returned(self):
        record = LowerCaseFieldWrapper(self.ss_record, "firstname", "surname")
        self.common_ss_test("firstname", "AbC", record, "abc")
        self.common_ss_test("surname", "AbC", record, "abc")
        self.common_ss_test("firstname", "", record, "")
        self.common_ss_test("surname", None, record, None)

    def test_GIVEN_empty_WHEN_nullify_wraped_THEN_None_returned(self):
        record = NullifingWrapper(self.ss_record, "mobile_phone", "home_phone")
        self.common_ss_test("mobile_phone", "123", record, "123")
        self.common_ss_test("mobile_phone", "", record, None)
        self.common_ss_test("home_phone", "123", record, "123")
        self.common_ss_test("home_phone", "", record, None)
        self.common_ss_test("home_phone", None, record, None)

    def test_GIVEN_yesno_field_WHEN_boolean_wraped_THEN_true_false_returned(self):
        record = BooleanFieldWrapper(self.ss_record, "active", "Data Prot email")
        self.common_ss_test("active", "Yes", record, True)
        self.common_ss_test("active", "yes", record, True)
        self.common_ss_test("active", "Y", record, True)
        self.common_ss_test("active", "No", record, False)
        self.common_ss_test("active", "no", record, False)
        self.common_ss_test("active", "n", record, False)
        self.common_ss_test("active", "x", record, False)
        self.common_ss_test("Data Prot email", "yes", record, True)
        self.common_ss_test("Data Prot email", "no", record, False)
        self.common_ss_test("Data Prot email", "zz", record, False)
        self.common_ss_test("Data Prot email", "", record, None)
        self.common_ss_test("Data Prot email", None, record, None)

    def test_GIVEN_model_instance_WHEN_model_wraped_THEN_fields_returned_through_dict_lookup(self):
        record = ModelRecordWrapper(self.player_instance)
        self.common_db_test("user.username", record, "xxx_test")
        self.common_db_test("user.first_name", record, "Foo")
        self.common_db_test("cell_phone", record, "07890 123456")


if __name__ == "__main__":

    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wsrc.site.settings.settings")

    import logging
    logging.basicConfig(format='%(asctime)-10s [%(levelname)s] %(message)s',datefmt="%Y-%m-%d %H:%M:%S")

    import django
    if hasattr(django, "setup"):
        django.setup()

    unittest.main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "ARI"
__date__ = "2014-02-16"
__version__ = "20140216"

import sys
from optparse import OptionParser
import json
import codecs
import re



# --- Utility classes ----------------------------------------------------------

class MyEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ColumnInfo):
            d = {}
            d['name'] = o.name
            d['sample'] = o.sample
            d['idx_start'] = o.start
            d['idx_end'] = o.end
            d['size'] = o.size
            d['type'] = ColumnInfo.type_tostr(o.type_detected)
            return d
        elif isinstance(o, ColumnDiff):
            d = {}
            d['name'] = o.name

            if not o.has_changes():
                d['changes'] = "none"
                return d

            # Change detected
            changes = []
            if o.has_changed_size():
                changes.append("size")
            if o.has_changed_nb_decs():
                changes.append("nb_decs")
            if o.has_changed_type():
                changes.append("type")

            d['changes'] = ", ".join(changes)

            d['type'] = "%s=>%s" % (ColumnInfo.type_tostr(o.first_col.type_detected), \
                              ColumnInfo.type_tostr(o.second_col.type_detected))
            d['size'] = "%s=>%s" % (o.first_col.size, o.second_col.size)

            # For TEXT specify default size direction
            if o.first_col.type_detected == ColumnInfo.T_TEXT and \
               o.second_col.type_detected == ColumnInfo.T_TEXT and \
               o.first_col.size != o.second_col.size:
                d['size_strip'] = "R"

            # For NUM types, give nb_decs
            type_d = o.second_col.type_detected
            if type_d == ColumnInfo.T_NUM  or type_d == ColumnInfo.T_NUM_V4:
                d['nb_decs'] = "%s=>%s" % (o.first_col.nb_decs, o.second_col.nb_decs)

            return d
        else:
            return json.JSONEncoder.default(self, o)


class ColumnInfo(object):
    '''
    Contains the description of a csv column.
    '''

    T_UNKNOW = 0
    T_NUM_V4, T_DATE_8, T_TEXT = 1, 2, 3
    T_NUM, T_DATE_DB2 = 11, 12

    def __init__(self, idx, sample, start, end):
        '''
        Constructor.
        '''

        self.idx = idx
        self.sample = sample
        self.start = start
        self.end = end

        # Computed values
        self.name = "C-%s" % self.idx
        self.type_detected = ColumnInfo.get_type(sample)
        self.size = self.end - self.start + 1

        if self.type_detected == ColumnInfo.T_NUM or \
           self.type_detected == ColumnInfo.T_NUM_V4:
            self.nb_decs = ColumnInfo.get_nb_decs(sample)
        else:
            self.nb_decs = 0

    @staticmethod
    def get_nb_decs(sample):
        '''
        Returns the number of decs after comma.
        '''

        sample = sample.replace(",", ".", 1)[::-1]
        idx = sample.find(".")
        if idx == -1:
            return 0
        return idx

    @staticmethod
    def get_type(sample):
        '''
        Returns the type of the sample.
        '''

        if len(sample) > 29:
            return ColumnInfo.T_TEXT
        if not sample.strip():
            return ColumnInfo.T_UNKNOW

        # Date
        if ColumnInfo.is_date_8(sample):
            return ColumnInfo.T_DATE_8
        if ColumnInfo.is_date_db2(sample):
            return ColumnInfo.T_DATE_DB2

        # Number
        if ColumnInfo.is_v4_num(sample):
            return ColumnInfo.T_NUM_V4
        if ColumnInfo.is_num(sample):
            return ColumnInfo.T_NUM

        # Text
        return ColumnInfo.T_TEXT

    @staticmethod
    def is_v4_num(sample):
        '''
        Tests if the string is in GP3 Numerical Format.
        Conditions :
            1. size == 27
            2. comma at pos. 16
            3. only digit
        '''

        # Gp3 number size
        if len(sample) != 27:
            return False
        # Always a ","
        sample = sample.replace(",", ".", 1)
        if sample[16] != ".":
            return False

        sample = sample.replace("-", " ", 1) \
                       .strip()
        # Empty number
        if not sample:
            return True
        # Test only digits
        return not not re.match(r"^[\d.]*$", sample)

    @staticmethod
    def is_num(sample):
        '''
        Tests if the string is in COBOL Numerical Format.
        Conditions :
            1. commma : "," or "."
            2. only one minus
            3. starts with a digit
        '''

        sample = sample.replace(",", ".", 1) \
                       .replace("-", " ", 1) \
                       .strip()
        if sample.find(".") == -1:
            return False
        return not not re.match(r"^\d[\d.]*$", sample)

    @staticmethod
    def is_date_8(sample):
        '''
        Tests if the string is in GP3 date format.
        Conditions :
            1. YYYYMMDD
        '''

        if len(sample) != 8:
            return False
        return not not re.match(r'^[12]\d{3}[01]\d[0123]\d+$', sample)

    @staticmethod
    def is_date_db2(sample):
        '''
        Tests if the string is in DB2 format.
        Conditions :
            1. YYYY-MM-DD
        '''

        if len(sample) != 10:
            return False
        return not not re.match(r'^[12]\d{3}-[01]\d-[0123]\d$', sample)

    @staticmethod
    def type_tostr(type_detected):
        if type_detected == ColumnInfo.T_UNKNOW:
            return "T_UNKNOW"
        elif type_detected == ColumnInfo.T_NUM_V4:
            return "T_NUM_V4"
        elif type_detected == ColumnInfo.T_DATE_8:
            return "T_DATE_8"
        elif type_detected == ColumnInfo.T_TEXT:
            return "T_TEXT"
        elif type_detected == ColumnInfo.T_NUM:
            return "T_NUM"
        elif type_detected == ColumnInfo.T_DATE_DB2:
            return "T_DATE_DB2"


class ColumnDiff(object):
    '''
    Contains the diff description of a column.
    '''

    def __init__(self, first_col, second_col):
        self.name = first_col.name
        self.first_col = first_col
        self.second_col = second_col

    def has_changes(self):
        return self.has_changed_size() or self.has_changed_type() or \
               self.has_changed_nb_decs()

    def changed_size(self):
        return self.second_col.size - self.first_col.size

    def has_changed_start(self):
        return self.second_col.start != self.first_col.start

    def has_changed_size(self):
        return self.changed_size() != 0

    def has_changed_type(self):
        is_num = (self.second_col.type_detected == self.first_col.type_detected) \
                 and (self.second_col.type_detected == ColumnInfo.T_NUM)
        is_diff = self.second_col.type_detected != self.first_col.type_detected
        return is_num or is_diff

    def has_changed_nb_decs(self):
        return self.second_col.nb_decs != self.first_col.nb_decs


# --- Actions ------------------------------------------------------------------

def get_cols_infos(csv_file):
    '''
    Describes cols informations.
    '''

    # Get CSV row with trailing ";"
    with open(csv_file, "rb") as f:
        row = f.next()
    if not row.rstrip().endswith(";"):
        row.append(";")

    results = []

    col_idx = 0
    start = 0
    idx = row.find(';', start)
    while idx != -1:
        col_idx = col_idx + 1
        next_start = idx
        col_data = row[start:idx]

        # Add ColumnInfo
        col_infos = ColumnInfo(col_idx, col_data, start, idx - 1)
        results.append(col_infos)

        # Next Item
        start = next_start + 1
        idx = row.find(';', start)

    return results

def display_unknows(col_infos):
    res = col_infos
    results = [ r for r in res if r.type_detected == ColumnInfo.T_UNKNOW ]

    print "# --- UNKNOWNS - START ---------------------------------------------"
    print json.dumps(results, sort_keys=True,
                     indent=4, separators=(',', ': '), cls=MyEncoder)
    print "# --- UNKNOWNS - END -----------------------------------------------"

def gen_date_changes(col_diffs):
    results = [ str(r.first_col.start) for r in col_diffs if
                    r.second_col.type_detected == ColumnInfo.T_DATE_DB2
                    and r.has_changed_type() ]
    str_idxs = " ".join(results)
    print "$UTILS/dateDB2.cexe $FIC %s >  $FIC_TMP" % str_idxs

def gen_reduce_changes(col_diffs):
    results = [ r.first_col.start for r in col_diffs if
                    r.second_col.type_detected == ColumnInfo.T_DATE_DB2
                    and r.has_changed_type() ]
    str_idxs = " ".join(results)
    print "$UTILS/sc_reduce_col.pexe $FIC_TRANS %s > $FIC_INFO" % str_format

def get_cols_diffs(first_csv, second_csv):
    '''
    Diffs 2 CSV files.
    '''
    results = []
    first_results = get_cols_infos(first_csv)
    second_results = get_cols_infos(second_csv)

    # Create ColumnDiffs and keep guessing types
    i = 0
    for first in first_results:
        second = second_results[i]

        # Better guess of TEXT types
        if second.type_detected == ColumnInfo.T_TEXT:
            first.type_detected = ColumnInfo.T_TEXT

        if second.type_detected == ColumnInfo.T_UNKNOW and \
            first.type_detected == ColumnInfo.T_TEXT:
            second.type_detected = ColumnInfo.T_TEXT

        # Better detection of UNKNOWN types
        if first.type_detected == second.type_detected and \
           first.type_detected == ColumnInfo.T_NUM and \
           first.nb_decs < 1 and second.nb_decs < 1:
            first.type_detected = ColumnInfo.T_UNKNOW
            second.type_detected = ColumnInfo.T_UNKNOW

        # Ignore No Changes
        diff = ColumnDiff(first, second)
        if diff.has_changes():
            results.append(diff)
        i = i + 1

    display_unknows(first_results)
    return results


# --- Main ---------------------------------------------------------------------

def main(options, args):
    '''
    Runs selected option, without validating args.
    Validation is done by the calling script.
    '''

    results = []

    if options.describe_csv:
        results = get_cols_infos(args[0])
    elif options.diff_csv:
        results = get_cols_diffs(args[0], args[1])
        gen_date_changes(results)
        # gen_reduce_changes(results)

    #print json.dumps(results, sort_keys=True,
    #                indent=4, separators=(',', ': '), cls=MyEncoder)
    print json.dumps(results, sort_keys=True, cls=MyEncoder).replace("},", "},\n")



if __name__ == '__main__':
    usage = "Usage: %prog [options] <file> [other-file]"
    parser = OptionParser(usage=usage, version=__version__)

    # Show CSV Infos
    parser.add_option("-i", "--show-infos",
                      action="store_const", const=1, default=0,
                      dest="describe_csv",
                      help="Show CSV Infos")

    # Diff two CSV files
    parser.add_option("-d", "--diff",
                      action="store_const", const=1, default=0,
                      dest="diff_csv",
                      help="Diff two CSV files")

    (options, args) = parser.parse_args()

    if len(sys.argv) <= 1:
        # DEBUG only
        #options.describe_csv = 1
        #args = ('<PATH_CSV_SHOW>',)
        options.diff_csv = 1
        args = ('<PATH_CSV_DIFF_BEFORE>',
                '<PATH_CSV_DIFF_AFTER>')


    # Check args
    if options.describe_csv + options.diff_csv > 1:
        parser.error("mutually exclusive options detected")
    elif options.describe_csv + options.diff_csv == 0:
        parser.error("no action specified")
    elif options.describe_csv and len(args) != 1:
        parser.error("display infos takes one arg")
    elif options.diff_csv and len(args) != 2:
        parser.error("diff_csv takes two args")

    # Processing
    main(options, args)
    sys.exit()

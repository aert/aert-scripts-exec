#!/gp3/rt/bin/python/latest/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "ARI"
__date__ = "2014-02-18"
__version__ = "20140218"

import sys
from optparse import OptionParser
import json
import codecs
import re


# --- Transform Engine ---------------------------------------------------------

class Transformer(object):
    """
    CSV Transform Engine.
    """

    def __init__(self, path_format, path_input, path_output):
        self.path_format = path_format
        self.path_input = path_input
        self.path_output = path_output

        self.action_descs = {}
        self.current_line = 0
        self.real_max_cols = 0

    def run(self):
        self.load_format()
        if self.real_max_cols == 0: return

        runner = ActionRunner(self.action_descs)

        with open(self.path_input, "rb") as fin:
            with open(self.path_output, "wt") as fout:
                for line_in in fin:
                    if len(line_in) < 3:
                        continue

                    # Convert !
                    row_out = runner.run(line_in.rstrip("\n"))
                    fout.write("%s\n" % ';'.join(row_out))

    def load_format(self):
        self.real_max_cols = self.estimate_column_count(self.path_input)
        if self.real_max_cols == 0: return

        with open(self.path_format, "rb") as fp:
            data = json.load(fp)
            for d in data:
                key = ActionDesc.get_col_id(d["name"])
                self.action_descs[key] = ActionDesc(d)

            # Filling Gaps
            max_cols = max(self.action_descs)
            for i in xrange(0, max_cols):
                if not i in self.action_descs:
                    d = {u"changes": u"none", u'name': u"C-%s" % i}
                    self.action_descs[i] = ActionDesc(d)
            max_cols = len(self.action_descs)
            if max_cols  < self.real_max_cols:
                for i in xrange(max_cols, self.real_max_cols):
                    d = {u"changes": u"none", u'name': u"C-%s" % i}
                    self.action_descs[i] = ActionDesc(d)


    @staticmethod
    def estimate_column_count(file_path):
        with open(file_path, "rb") as f:
            try:
                row = f.next()
            except StopIteration:
                return 0
        return len(row.rstrip().split(";"))


class ActionRunner(object):
    """
    Converts an input row to a destination row using ActionDesc.
    """

    def __init__(self, action_descs):
        self.action_descs = action_descs
        self.nb_actions = len(action_descs)
        self.count = 0

        self.actions_avails = {
            "none": self.action_none,
            "ignore": self.action_ignore,
            "type": self.action_type,
            "size": self.action_size,
            "nb_decs": self.action_nb_decs,
            "move_before": self.action_move_before,
            "move_after": self.action_move_after,
        }

    def run(self, line_in):
        """
        Applies action for the row, using the appropriate ActionDesc.
        """
        self.count = self.count + 1
        dict_in = ColumnDict(line_in)
        dict_out = dict_in.copy()

        if dict_in.length < self.nb_actions:
            raise Exception, "[E] Line %s: Invalid number of columns: %s, expected: %s" % (self.count, dict_in.length, self.nb_actions)

        # Process columns
        for i in xrange(0, self.nb_actions):
            self.process_column(i, dict_in, dict_out)

        # End
        return dict_out.to_row()

    def process_column(self, col_idx, dict_in, dict_out):
        """ Transforms indicated column. """
        action_desc = self.action_descs[col_idx]

        # Run all transformations
        for chg in action_desc.changes_list:
            action_fn = self.actions_avails[chg](action_desc, dict_in, dict_out)

    def action_none(self, action_desc, dict_in, dict_out):
        """ Do nothing. """
        pass

    def action_ignore(self, action_desc, dict_in, dict_out):
        dict_out.ignore(action_desc.idx)

    def action_type(self, action_desc, dict_in, dict_out):
        """
        Managed cases:
            T_NUM_=>T_NUM
            T_NUM_V4=>T_NUM
            T_DATE_8=>T_DATE_DB2
        """
        is_conv_to_num = (action_desc.type_old == "T_NUM_V4" and action_desc.type_new == "T_NUM")
        is_conv_to_db2 = (action_desc.type_old == "T_DATE_8" and action_desc.type_new == "T_DATE_DB2")
        is_conv_between_num = (action_desc.type_old == "T_NUM" and action_desc.type_new == "T_NUM")

        is_managed = is_conv_to_num or is_conv_to_db2 or is_conv_between_num
        if not is_managed:
            return

        # Case size_num : T_NUM_=>T_NUM
        if is_conv_between_num:
            nb_decs_old = action_desc.nb_decs_old
            nb_decs_new = action_desc.nb_decs_new
            size_old = action_desc.size_old
            size_new = action_desc.size_new
            dict_out.conv_between_num(action_desc.idx, size_old, size_new, nb_decs_old, nb_decs_new)
            return

        # Case is_conv_to_db2 : T_DATE_8=>T_DATE_DB2
        if is_conv_to_db2:
            dict_out.conv_to_db2(action_desc.idx)
            return

        # Case is_conv_to_num : T_NUM_V4=>T_NUM
        nb_decs_old = action_desc.nb_decs_old
        nb_decs_new = action_desc.nb_decs_new
        size_old = action_desc.size_old
        size_new = action_desc.size_new

        dict_out.conv_to_num(action_desc.idx, size_old, size_new, nb_decs_old, nb_decs_new)


    def action_size(self, action_desc, dict_in, dict_out):
        """
        Managed cases:
            T_TEXT=>T_TEXT
        """

        # Case size_text : T_TEXT=>T_TEXT
        if action_desc.type_old != "T_TEXT" or action_desc.chg_type:
            return

        count = abs(action_desc.size_new - action_desc.size_old)
        is_right = action_desc.size_strip == "R"
        is_left = action_desc.size_strip == "L"
        if is_right:
            dict_out.rtrim(action_desc.idx, count)
        elif is_left:
            dict_out.ltrim(action_desc.idx, count)
        else:
            dict_out.auto_trim(action_desc.idx, count)

    def action_nb_decs(self, action_desc, dict_in, dict_out):
        """ Ignore, handled by action_type. """
        pass

    def action_move_before(self, action_desc, dict_in, dict_out):
        pass

    def action_move_after(self, action_desc, dict_in, dict_out):
        pass


class ColumnDict(object):
    REMOVED = "---"

    def __init__(self, line):
        if line is None:
            return

        self.col_names = []
        self.col_values = []
        i = 0
        for col_data in line.split(";"):
            i = i + 1
            self.col_names.append("C-%s" % i)
            self.col_values.append(col_data)
        self.length = i

    def rtrim(self, idx, count):
        self.col_values[idx] = self.col_values[idx][:-count]

    def ltrim(self, idx, count):
        self.col_values[idx] = self.col_values[idx][count:]

    def auto_trim(self, idx, count):
        value = self.col_values[idx]
        if value[0:count-1].strip() == "":
            self.ltrim(idx, count)
        else:
            self.rtrim(idx, count)

    def conv_to_db2(self, idx):
        value = self.col_values[idx].strip()
        if value == "":
            self.col_values[idx] = " " * 10
            return

        self.check(len(value) == 8, idx)
        self.col_values[idx] = "%s-%s-%s" % (value[0:4], value[4:6], value[6:])

    def conv_between_num(self, idx, size_old, size_new, nb_decs_old, nb_decs_new):
        self.conv_to_num(idx, size_old, size_new, nb_decs_old, nb_decs_new)

    def conv_to_num(self, idx, size_old, size_new, nb_decs_old, nb_decs_new):
        value = self.col_values[idx].replace(".", ",")

        if value.replace(",", "").replace("-", "").strip() == "":
            self.col_values[idx] = " " * size_new
            return

        self.check(len(value) == size_old, idx)
        self.check(value[-nb_decs_old-1] == ",", idx)
        self.check(value.count("-") < 2, idx)
        self.check(value.count(",") == 1, idx)

        comma_idx = value.find(",")
        neg_idx = value[0:comma_idx].find("-")

        dec_part = value[-nb_decs_old:]
        if neg_idx == -1:
            int_part = value[0:comma_idx]
        else:
            int_part = value[neg_idx + 1: comma_idx]

        int_part = int_part.strip().lstrip("0")
        dec_part = dec_part.strip()

        if int_part == "": int_part = "0"
        if dec_part == "": dec_part = "0"

        self.check(int_part.isdigit(), idx)
        self.check(dec_part.isdigit(), idx)

        # ### Convert !

        dec_offset_add = nb_decs_new - len(dec_part)
        int_offset_add = (size_new-2-nb_decs_new) - len(int_part)

        # case of the positive int wich fills all size
        is_full_positive_int = int_offset_add == -1 and neg_idx == -1

        self.check(int_offset_add >= 0 or is_full_positive_int, idx)

        if dec_offset_add > 0:
            dec_part = dec_part + "0" * abs(dec_offset_add)
        else:
            dec_part = dec_part[0:nb_decs_new]

        if not is_full_positive_int:
            int_part =  "0" * int_offset_add + int_part
            if neg_idx != -1: int_part =  "-" + int_part
            else: int_part =  " " + int_part

        self.col_values[idx] = int_part + "," + dec_part


    def ignore(self, idx):
        """ Removes col by name or index."""
        #if isinstance(key, basestring):
        #    try: idx = self.col_names.index(key)
        #    except ValueError: return
        self.col_names[idx] = self.REMOVED

    def copy(self):
        result = ColumnDict(None)
        result.col_names = self.col_names[:]
        result.col_values = self.col_values[:]
        result.length = self.length
        return result

    def to_row(self):
        results = []
        for i in xrange(0, self.length):
            if self.col_names[i] != self.REMOVED:
                results.append(self.col_values[i])
        return results

    def check(self, condition, idx):
        if not condition:
            raise Exception, "[E] [%s=\"%s\"] - bad value." % (self.col_names[idx], self.col_values[idx])


class ActionDesc(object):
    """
    Stores Format Data.
    """

    def __init__(self, data):
        """
        Converts data to fields.
        """

        for key in data:
            if isinstance(data[key], basestring):
                data[key] = data[key].replace(' ', '')

        self.name = data["name"]
        self.changes = data["changes"]
        self.changes_list = data["changes"].split(",")
        self.idx = self.get_col_id(data["name"])

        if self.changes == "none":
            self.chg_none = True
            return
        self.chg_none = False

        # Changes Flags
        chglist = self.changes.split(",")
        self.chg_size = "size" in chglist
        self.chg_type = "type" in chglist
        self.chg_nb_decs = "nb_decs" in chglist
        self.chg_move_before = "move_before" in chglist
        self.chg_move_after = "move_after" in chglist
        self.chg_ignore = "ignore" in chglist

        # .. sizes
        self.size_old, self.size_new = self.parse_changed_int(data["size"])
        if "size_strip" in data:
            self.size_strip = data["size_strip"]
        else: self.size_strip = None

        # .. types
        self.type_old, self.type_new = self.parse_changed_str(data["type"])

        # .. nb_decs
        if data.has_key("nb_decs"):
            self.nb_decs_old, self.nb_decs_new = self.parse_changed_int(data["nb_decs"])

        # .. move_before
        if data.has_key("move_before"):
            self.move_before = self.get_col_id(data["move_before"])

        # .. move_after
        if data.has_key("move_after"):
            self.move_after = self.get_col_id(data["move_after"])

        # End
        self.validate()

    def validate(self):
        self.check(self.size_old != None and self.size_new != None, "size")
        self.check(self.type_old != None and self.type_new != None, "type")

        if self.size_strip is not None:
            self.check(self.size_strip in ["A", "R", "L"], "size_strip")
        if self.chg_nb_decs:
            self.check(self.nb_decs_old != None and self.nb_decs_new != None, "nb_decs")
        if self.chg_move_before:
            self.check(self.move_before != None, "move_before")
        if self.chg_move_after:
            self.check(self.move_after != None, "move_after")

        chglist = self.changes.split(",")
        valid = ["size", "size_strip", "type", "nb_decs", "move_before", "move_after", "ignore"]
        invalid = [x for x in chglist if x not in valid]
        self.check(len(invalid) == 0, "changes=(%s)" % ", ".join(invalid))

    def check(self, condition, msg):
        if not condition:
            raise Exception, "[E] [%s] %s - bad param." % (self.name, msg)

    @staticmethod
    def parse_changed_int(value):
        """
        Decodes value of "Old=>New".
        """
        old, new = value.split("=>")
        old = int(old)
        new = int(new)
        return (old, new)

    @staticmethod
    def parse_changed_str(value):
        """
        Decodes value of "Old=>New".
        """
        old, new = value.split("=>")
        return (old, new)

    @staticmethod
    def get_col_id(name):
        return int(name[2:]) - 1


# --- Main ---------------------------------------------------------------------

def main(options, args):
    '''
    Runs selected option, without validating args.
    Validation is done by the calling script.
    '''

    # Get Args
    path_format, path_input, path_output = args
    if not path_output:
        path_output = sys.stdout

    # Run
    transformer = Transformer(path_format, path_input, path_output)
    transformer.run()


if __name__ == '__main__':
    usage = "Usage: %prog <format_file> <input-file> [output-file]"
    parser = OptionParser(usage=usage, version=__version__)

    (options, args) = parser.parse_args()

    if len(sys.argv) <= 1:
        # DEBUG MODE
        args = ('<format_file>',
                '<input-file>',
                '[output-file]')


    # Check args
    if len(args) != 3 and len(args) != 2:
        parser.error("Arguments incorrects.")

    # Processing
    main(options, args)
    sys.exit()

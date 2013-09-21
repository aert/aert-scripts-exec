#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from optparse import OptionParser
import json
import codecs


def run(egrep, file_path):

    matches = egrep.split('|')
    results = {}
    for match in matches:
        results[match] = ''
    with codecs.open(file_path, "r", encoding='latin-1') as f_in:
        for line in f_in:
            line_in = line.rstrip('\r\n').rstrip('\n')
            res = line_in.split(':', 1)
            if len(res) < 2:
                continue
            path, expr = tuple(res)
            for match in matches:
                if match in expr:
                    results[match] = "%s\n%s" % (results[match], line_in)

    print json.dumps(results, sort_keys=True,
                     indent=4, separators=(',', ': '))
    print "Not FOUND:"
    for match in matches:
        if len(results[match]) < 2:
            print '    %s' % match


# Main Entry Point
if __name__ == '__main__':
    usage = "Usage: %prog <egrep_expr> <grep_output>"
    parser = OptionParser(usage=usage, version="%prog 1.0")

    (options, args) = parser.parse_args()

    if len(sys.argv) != 3:
        parser.print_help()

    run(args[0], args[1])

    sys.exit()

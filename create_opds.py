#!/usr/bin/python

import os, shutil, sys
from argparse import ArgumentParser

from fbreader.opds import ErrorHandler, OpdsBuilder

def parse_command_line():
    parser = ArgumentParser(
        description='''FBReader.ORG OPDS creation tool'''
    )
    parser.add_argument(
        'description_file',
        help='file containing catalog description and book links list'
    )
    parser.add_argument(
        '-o',
        metavar='output_dir',
        dest='output_dir',
        default='./opds',
        help='directory where to create OPDS data (default = ./opds)'
    )
    parser.add_argument(
        '-f',
        dest='override',
        action='store_true',
        default=False,
        help='override existing OPDS directory'
    )
    params = parser.parse_args(sys.argv[1:])
    return params

class CommandLineErrorHandler(ErrorHandler):
    def warning(self, pattern, *params):
        print 'Warning: ' + pattern % params

    def fatal(self, pattern, *params):
        exit('Fatal error: ' + pattern % params)

if __name__ == '__main__':
    error_handler = CommandLineErrorHandler()

    params = parse_command_line()
    if os.path.exists(params.output_dir):
        if params.override:
            shutil.rmtree(params.output_dir)
        else:
            error_handler.fatal('%s already exists', params.output_dir)
    os.makedirs(params.output_dir)

    builder = OpdsBuilder(output_dir=params.output_dir, error_handler=error_handler)
    builder.build(params.description_file)

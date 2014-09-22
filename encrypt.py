#!/usr/bin/python

import shutil, string, sys, tempfile
from argparse import ArgumentParser

from fbreader.format.epub import EPub

def verify_key(key, name):
    if len(key) != 32:
        raise Exception('Incorrect %s length %d, 32 expected' % (name, len(key)))
    for sym in key:
        if not sym in string.hexdigits:
            raise Exception('Incorrect character %s in %s' % (sym, name))

def parse_command_line():
    parser = ArgumentParser(
        description='Marlin ePub encryption tool'
    )
    parser.add_argument(
        '-s',
        '--keep-unencrypted',
        dest='keep_unencrypted',
        metavar='keep_unencrypted',
        nargs='*',
        help='entry to keep not encrypted (tool encrypts all entries except cover by default)'
    )
    parser.add_argument(
        '-k',
        dest='key',
        metavar='key',
        required=True,
        help='encryption key (32-digit hex number)'
    )
    parser.add_argument(
        '-ci',
        dest='content_id',
        metavar='content_id',
        required=True,
        help='content id'
    )
    parser.add_argument(
        'epub',
        help='name of ePub file to encrypt'
    )
    params = parser.parse_args(sys.argv[1:])
    verify_key(params.key, 'key')
    return params

if __name__ == '__main__':
    params = parse_command_line()
    working_dir = tempfile.mkdtemp(dir='.')
    try:
        epub = EPub(params.epub)
        epub.encrypt(params.key, params.content_id, working_dir, files_to_keep=params.keep_unencrypted)
    finally:
        shutil.rmtree(working_dir)

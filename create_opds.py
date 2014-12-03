#!/usr/bin/python

import hashlib, os, re, shutil, sys, tempfile, urllib2
from argparse import ArgumentParser
from datetime import datetime
from lxml import etree

from fbreader.format.epub import EPub
from fbreader.format.mimetype import Mimetype

def parse_command_line():
    parser = ArgumentParser(
        description='OPDS creation tool'
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

NS_ATOM         = 'http://www.w3.org/2005/Atom'
NS_DUBLIN_CORE  = 'http://purl.org/dc/terms/'
NS_CALIBRE      = 'http://calibre.kovidgoyal.net/2009/metadata'

ACQ_OPEN_ACCESS = 'http://opds-spec.org/acquisition/open-access'

def utf8(text):
    if isinstance(text, str):
        return unicode(text, encoding='utf-8')
    return text

def timestamp():
    return datetime.now().replace(microsecond=0).isoformat()

def hash(file_name):
    sha = hashlib.sha1()
    with open(file_name, 'rb') as istream:
        data = istream.read(8192)
        while data:
            sha.update(data)
            data = istream.read(8192)
    return sha.hexdigest()

def add_info(root, info):
    etree.SubElement(root, etree.QName(NS_ATOM, 'updated')).text = timestamp()
    for key in ('id', 'title', 'description', 'icon'):
        if info.has_key(key):
            etree.SubElement(root, etree.QName(NS_ATOM, key)).text = info.get(key)
        else:
            print 'Warning: feed "%s" attribute is not specified' % key
    author = etree.SubElement(root, etree.QName(NS_ATOM, 'author'))
    for key in ('name', 'uri', 'email'):
        author_key = 'author_' + key
        if info.has_key(author_key):
            etree.SubElement(author, etree.QName(NS_ATOM, key)).text = info.get(author_key)
        else:
            print 'Warning: feed "%s" attribute is not specified' % author_key

def add_entry(root, urls, working_dir):
    file_name = working_dir + '/1'
    with open(file_name, 'wb') as f:
        f.write(urllib2.urlopen(urls[0]).read())
    book = EPub(file_name)
    entry = etree.SubElement(root, etree.QName(NS_ATOM, 'entry'))
    etree.SubElement(entry, etree.QName(NS_ATOM, 'id')).text = 'book:id:%s' % hash(file_name)
    # TODO: use real update time
    etree.SubElement(entry, etree.QName(NS_ATOM, 'updated')).text = timestamp()
    etree.SubElement(entry, etree.QName(NS_ATOM, 'title')).text = book.title
    if book.language_code:
        etree.SubElement(entry, etree.QName(NS_DUBLIN_CORE, 'language')).text = book.language_code
    if book.series_info:
        title = book.series_info.get('title')
        if title:
            etree.SubElement(entry, etree.QName(NS_CALIBRE, 'series')).text = title
        index = book.series_info.get('index')
        if index:
            etree.SubElement(entry, etree.QName(NS_CALIBRE, 'series_index')).text = index
    if book.description:
        etree.SubElement(entry, etree.QName(NS_ATOM, 'summary'), type='html').text = book.description
    for author in book.authors:
        a = etree.SubElement(entry, etree.QName(NS_ATOM, 'author'))
        etree.SubElement(a, etree.QName(NS_ATOM, 'name')).text = author.get('name')
        etree.SubElement(a, etree.QName(NS_ATOM, 'uri')).text = 'author:id:' + author.get('sortkey')
    for tag in book.tags:
        etree.SubElement(entry, etree.QName(NS_ATOM, 'category'), term=tag, label=tag)
#  <link href='{{ b.thumbnail.url | urlencode }}' type='{{ b.thumbnail.mimetype }}' rel='http://opds-spec.org/thumbnail'/>
#  <link href='{{ b.cover.url | urlencode }}' type='{{ b.cover.mimetype }}' rel='http://opds-spec.org/cover'/>
    for u in urls:
        # TODO: correct type
        mime = Mimetype.EPUB
        etree.SubElement(entry, etree.QName(NS_ATOM, 'link'), href=utf8(u), type=mime, rel=ACQ_OPEN_ACCESS)

def create_opds(description_file, output_dir, working_dir):
    SECTION_PATTERN = re.compile('^\[(.+)\]$')
    section = None

    namespaces = {
        None      :   NS_ATOM,
        'dc'      :   NS_DUBLIN_CORE,
        'calibre' :   NS_CALIBRE
    }
    root = etree.Element(etree.QName(NS_ATOM, 'feed'), nsmap=namespaces)
    with open(description_file) as data:
        info = {}
        urls = []
        for line in [l.strip() for l in data]:
            matcher = SECTION_PATTERN.match(line)
            if matcher:
                section = matcher.group(1)
                if info:
                    add_info(root, info)
                    info = {}
                if urls:
                    add_entry(root, urls, working_dir)
                    urls = []
            elif section == 'feed':
                data = line.split('=')
                if len(data) == 2:
                    info[data[0].strip()] = utf8(data[1].strip())
            elif section == 'book':
                urls.append(line)
        if urls:
            add_entry(root, urls, working_dir)
    with open(output_dir + '/catalog.xml', 'w') as pfile:
        etree.ElementTree(root).write(pfile, encoding='utf-8', xml_declaration=True, pretty_print=True)

if __name__ == '__main__':
    params = parse_command_line()
    if os.path.exists(params.output_dir):
        if params.override:
            shutil.rmtree(params.output_dir)
        else:
            exit('Error: %s already exists' % params.output_dir)
    os.makedirs(params.output_dir)

    working_dir = tempfile.mkdtemp(dir='.')
    try:
        create_opds(params.description_file, params.output_dir, working_dir)
    finally:
        shutil.rmtree(working_dir)

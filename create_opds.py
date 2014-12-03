#!/usr/bin/python

import hashlib, os, re, shutil, sys, tempfile, urllib2
from argparse import ArgumentParser
from datetime import datetime
from lxml import etree
from PIL import Image

from fbreader.format import create_bookfile, detect_mime

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

NS_ATOM         = 'http://www.w3.org/2005/Atom'
NS_DUBLIN_CORE  = 'http://purl.org/dc/terms/'
NS_CALIBRE      = 'http://calibre.kovidgoyal.net/2009/metadata'

REL_ACQ_OPEN_ACCESS = 'http://opds-spec.org/acquisition/open-access'
REL_COVER = 'http://opds-spec.org/cover'
REL_THUMBNAIL = 'http://opds-spec.org/thumbnail'

def utf8(text):
    if isinstance(text, str):
        return unicode(text, encoding='utf-8')
    return text

def timestamp():
    return datetime.now().replace(microsecond=0).isoformat()

def file_hash(file_name):
    sha = hashlib.sha1()
    with open(file_name, 'rb') as istream:
        data = istream.read(8192)
        while data:
            sha.update(data)
            data = istream.read(8192)
    return sha.hexdigest()

def string_hash(string):
    sha = hashlib.sha1()
    if isinstance(string, unicode):
        string = string.encode(encoding='utf-8')
    sha.update(string)
    return sha.hexdigest()

def warning(pattern, *params):
    print 'Warning: ' + pattern % params

def fatal(pattern, *params):
    exit('Fatal error: ' + pattern % params)

def add_info(root, info):
    etree.SubElement(root, etree.QName(NS_ATOM, 'updated')).text = timestamp()
    for key in ('id', 'title', 'subtitle', 'icon'):
        if info.has_key(key):
            etree.SubElement(root, etree.QName(NS_ATOM, key)).text = info.get(key)
        else:
            warning('feed "%s" attribute is not specified', key)
    author = etree.SubElement(root, etree.QName(NS_ATOM, 'author'))
    for key in ('name', 'uri', 'email'):
        author_key = 'author_' + key
        if info.has_key(author_key):
            etree.SubElement(author, etree.QName(NS_ATOM, key)).text = info.get(author_key)
        else:
            warning('feed "%s" attribute is not specified', author_key)

def add_entry(root, urls, output_dir, working_dir):
    book_map = {}
    for count, u in enumerate(urls):
        file_name = working_dir + '/%s' % count
        try:
            with open(file_name, 'wb') as f:
                request = urllib2.Request(u, headers={ 'User-Agent': 'FBReader.ORG OPDS creator' })
                f.write(urllib2.urlopen(request).read())
            try:
                book_map[u] = create_bookfile(file_name, u)
            except:
                warning('cannot parse file %s, skipping', u)
        except:
            warning('cannot download %s, skipping', u)
    if not book_map:
        return

    for u in urls:
        if book_map.has_key(u):
            book = book_map.get(u)
            break
    book_id = file_hash(book.path)

    entry = etree.SubElement(root, etree.QName(NS_ATOM, 'entry'))
    etree.SubElement(entry, etree.QName(NS_ATOM, 'id')).text = 'book:id:%s' % book_id
    # TODO: use real update time
    etree.SubElement(entry, etree.QName(NS_ATOM, 'updated')).text = timestamp()
    etree.SubElement(entry, etree.QName(NS_ATOM, 'title')).text = utf8(book.title)
    if book.language_code:
        etree.SubElement(entry, etree.QName(NS_DUBLIN_CORE, 'language')).text = book.language_code
    if book.series_info:
        title = book.series_info.get('title')
        if title:
            etree.SubElement(entry, etree.QName(NS_CALIBRE, 'series')).text = utf8(title)
        index = book.series_info.get('index')
        if index:
            etree.SubElement(entry, etree.QName(NS_CALIBRE, 'series_index')).text = index
    if book.description:
        etree.SubElement(entry, etree.QName(NS_ATOM, 'summary'), type='html').text = utf8(book.description)
    for name in [author.get('name') for author in book.authors]:
        a = etree.SubElement(entry, etree.QName(NS_ATOM, 'author'))
        etree.SubElement(a, etree.QName(NS_ATOM, 'name')).text = utf8(name)
        etree.SubElement(a, etree.QName(NS_ATOM, 'uri')).text = 'author:id:' + string_hash(name)
    for tag in book.tags:
        etree.SubElement(entry, etree.QName(NS_ATOM, 'category'), term=tag, label=tag)
    cover = book.extract_cover(working_dir)
    if cover:
        try:
            path = working_dir + '/' + cover
            image = Image.open(path).convert('RGB')
            mime = detect_mime(path)
            ext = mime[6:] if len(mime) > 7 and mime.startswith('image/') else 'jpeg'
            url = book_id + '.' + ext
            shutil.copy(path, output_dir + '/' + url)
            etree.SubElement(entry, etree.QName(NS_ATOM, 'link'), href=url, type=mime, rel=REL_COVER)
            if image.size[0] > 160:
                width = 128
                height = int(float(width) * image.size[1] / image.size[0] + .5)
                image.thumbnail((width, height), Image.ANTIALIAS)
                thumbnail_path = working_dir + '/thumbnail.jpeg'
                image.save(thumbnail_path, 'JPEG')
                mime = 'image/jpeg'
                url = book_id + '.thumbnail.jpeg'
                shutil.copy(thumbnail_path, output_dir + '/' + url)
            etree.SubElement(entry, etree.QName(NS_ATOM, 'link'), href=url, type=mime, rel=REL_THUMBNAIL)
        except:
            pass
    for u in urls:
        b = book_map.get(u)
        if b:
            etree.SubElement(entry, etree.QName(NS_ATOM, 'link'), href=utf8(u), type=b.mimetype, rel=REL_ACQ_OPEN_ACCESS)

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
        for count, line in enumerate([l.strip() for l in data]):
            if not line or line.startswith('#'):
                continue
            matcher = SECTION_PATTERN.match(line)
            if matcher:
                new_section = matcher.group(1)
                if section == None:
                    if new_section != 'feed':
                        fatal('line %s: first section must be [feed]', count + 1)
                else:
                    if new_section == 'feed':
                        fatal('line %s: duplicate [feed] section', count + 1)
                    elif new_section != 'book':
                        fatal('line %s: unknown [%s] section', count + 1, new_section)
                section = new_section
                if info:
                    add_info(root, info)
                    info = {}
                if urls:
                    add_entry(root, urls, output_dir, working_dir)
                    urls = []
            else:
                data = line.split('=')
                if len(data) != 2:
                    fatal('invalid format in line %s', count + 1)
                key = data[0].strip()
                value = data[1].strip()
                if section == 'feed':
                    info[key] = utf8(value)
                elif section == 'book' and key == 'url':
                    urls.append(value)
        if urls:
            add_entry(root, urls, output_dir, working_dir)
    with open(output_dir + '/catalog.xml', 'w') as pfile:
        etree.ElementTree(root).write(pfile, encoding='utf-8', xml_declaration=True, pretty_print=True)

if __name__ == '__main__':
    params = parse_command_line()
    if os.path.exists(params.output_dir):
        if params.override:
            shutil.rmtree(params.output_dir)
        else:
            fatal('%s already exists', params.output_dir)
    os.makedirs(params.output_dir)

    working_dir = tempfile.mkdtemp(dir='.')
    try:
        create_opds(params.description_file, params.output_dir, working_dir)
    finally:
        shutil.rmtree(working_dir)

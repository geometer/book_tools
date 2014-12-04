import hashlib, re, shutil, tempfile, urllib2
from abc import abstractmethod, ABCMeta
from datetime import datetime
from lxml import etree
from PIL import Image

from fbreader.format import create_bookfile, detect_mime

NS_ATOM         = 'http://www.w3.org/2005/Atom'
NS_DUBLIN_CORE  = 'http://purl.org/dc/terms/'
NS_CALIBRE      = 'http://calibre.kovidgoyal.net/2009/metadata'

REL_ACQ_OPEN_ACCESS = 'http://opds-spec.org/acquisition/open-access'
REL_COVER = 'http://opds-spec.org/cover'
REL_THUMBNAIL = 'http://opds-spec.org/thumbnail'

class ErrorHandler(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def warning(self, pattern, *params):
        pass

    @abstractmethod
    def fatal(self, pattern, *params):
        pass

class OpdsBuilder(object):
    def __init__(self, output_dir, error_handler):
        self.__output_dir = output_dir
        self.__error_handler = error_handler
        
    def build(self, description_file):
        self.__working_dir = tempfile.mkdtemp(dir=self.__output_dir)
        try:
            self.__build(description_file)
        finally:
            shutil.rmtree(self.__working_dir)

    def __build(self, description_file):
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
                            self.__error_handler.fatal('line %s: first section must be [feed]', count + 1)
                    else:
                        if new_section == 'feed':
                            self.__error_handler.fatal('line %s: duplicate [feed] section', count + 1)
                        elif new_section != 'book':
                            self.__error_handler.fatal('line %s: unknown [%s] section', count + 1, new_section)
                    section = new_section
                    if info:
                        self.__add_info(root, info)
                        info = {}
                    if urls:
                        self.__add_entry(root, urls)
                        urls = []
                else:
                    data = line.split('=')
                    if len(data) != 2:
                        self.__error_handler.fatal('invalid format in line %s', count + 1)
                    key = data[0].strip()
                    value = data[1].strip()
                    if section == 'feed':
                        info[key] = OpdsBuilder.__utf8(value)
                    elif section == 'book' and key == 'url':
                        urls.append(value)
            if urls:
                self.__add_entry(root, urls)
        with open(self.__output_dir + '/catalog.xml', 'w') as pfile:
            etree.ElementTree(root).write(pfile, encoding='utf-8', xml_declaration=True, pretty_print=True)

    def __add_entry(self, root, urls):
        book_map = {}
        for count, u in enumerate(urls):
            file_name = self.__working_dir + '/%s' % count
            try:
                with open(file_name, 'wb') as f:
                    request = urllib2.Request(u, headers={ 'User-Agent': 'FBReader.ORG OPDS creator' })
                    f.write(urllib2.urlopen(request).read())
                try:
                    book_map[u] = create_bookfile(file_name, u)
                except:
                    self.__error_handler.warning('cannot parse file %s, skipping', u)
            except:
                self.__error_handler.warning('cannot download %s, skipping', u)
        if not book_map:
            return

        for u in urls:
            if book_map.has_key(u):
                book = book_map.get(u)
                break
        book_id = OpdsBuilder.__file_hash(book.path)

        entry = etree.SubElement(root, etree.QName(NS_ATOM, 'entry'))
        etree.SubElement(entry, etree.QName(NS_ATOM, 'id')).text = 'book:id:%s' % book_id
        # TODO: use real update time
        etree.SubElement(entry, etree.QName(NS_ATOM, 'updated')).text = OpdsBuilder.__timestamp()
        etree.SubElement(entry, etree.QName(NS_ATOM, 'title')).text = OpdsBuilder.__utf8(book.title)
        if book.language_code:
            etree.SubElement(entry, etree.QName(NS_DUBLIN_CORE, 'language')).text = book.language_code
        if book.series_info:
            title = book.series_info.get('title')
            if title:
                etree.SubElement(entry, etree.QName(NS_CALIBRE, 'series')).text = OpdsBuilder.__utf8(title)
            index = book.series_info.get('index')
            if index:
                etree.SubElement(entry, etree.QName(NS_CALIBRE, 'series_index')).text = index
        if book.description:
            etree.SubElement(entry, etree.QName(NS_ATOM, 'summary'), type='html').text = OpdsBuilder.__utf8(book.description)
        for name in [author.get('name') for author in book.authors]:
            a = etree.SubElement(entry, etree.QName(NS_ATOM, 'author'))
            etree.SubElement(a, etree.QName(NS_ATOM, 'name')).text = OpdsBuilder.__utf8(name)
            etree.SubElement(a, etree.QName(NS_ATOM, 'uri')).text = 'author:id:' + OpdsBuilder.__string_hash(name)
        for tag in book.tags:
            etree.SubElement(entry, etree.QName(NS_ATOM, 'category'), term=tag, label=tag)
        cover = book.extract_cover(self.__working_dir)
        if cover:
            try:
                path = self.__working_dir + '/' + cover
                image = Image.open(path).convert('RGB')
                mime = detect_mime(path)
                ext = mime[6:] if len(mime) > 7 and mime.startswith('image/') else 'jpeg'
                url = book_id + '.' + ext
                shutil.copy(path, self.__output_dir + '/' + url)
                etree.SubElement(entry, etree.QName(NS_ATOM, 'link'), href=url, type=mime, rel=REL_COVER)
                if image.size[0] > 160:
                    width = 128
                    height = int(float(width) * image.size[1] / image.size[0] + .5)
                    image.thumbnail((width, height), Image.ANTIALIAS)
                    thumbnail_path = self.__working_dir + '/thumbnail.jpeg'
                    image.save(thumbnail_path, 'JPEG')
                    mime = 'image/jpeg'
                    url = book_id + '.thumbnail.jpeg'
                    shutil.copy(thumbnail_path, self.__output_dir + '/' + url)
                etree.SubElement(entry, etree.QName(NS_ATOM, 'link'), href=url, type=mime, rel=REL_THUMBNAIL)
            except:
                pass
        for u in urls:
            b = book_map.get(u)
            if b:
                etree.SubElement(entry, etree.QName(NS_ATOM, 'link'), href=OpdsBuilder.__utf8(u), type=b.mimetype, rel=REL_ACQ_OPEN_ACCESS)

    def __add_info(self, root, info):
        etree.SubElement(root, etree.QName(NS_ATOM, 'updated')).text = OpdsBuilder.__timestamp()
        for key in ('id', 'title', 'subtitle', 'icon'):
            if info.has_key(key):
                etree.SubElement(root, etree.QName(NS_ATOM, key)).text = info.get(key)
            else:
                self.__error_handler.warning('feed "%s" attribute is not specified', key)
        author = etree.SubElement(root, etree.QName(NS_ATOM, 'author'))
        for key in ('name', 'uri', 'email'):
            author_key = 'author_' + key
            if info.has_key(author_key):
                etree.SubElement(author, etree.QName(NS_ATOM, key)).text = info.get(author_key)
            else:
                self.__error_handler.warning('feed "%s" attribute is not specified', author_key)

    @staticmethod
    def __utf8(text):
        if isinstance(text, str):
            return unicode(text, encoding='utf-8')
        return text

    @staticmethod
    def __timestamp():
        return datetime.now().replace(microsecond=0).isoformat()

    @staticmethod
    def __file_hash(file_name):
        sha = hashlib.sha1()
        with open(file_name, 'rb') as istream:
            data = istream.read(8192)
            while data:
                sha.update(data)
                data = istream.read(8192)
        return sha.hexdigest()

    @staticmethod
    def __string_hash(string):
        sha = hashlib.sha1()
        if isinstance(string, unicode):
            string = string.encode(encoding='utf-8')
        sha.update(string)
        return sha.hexdigest()

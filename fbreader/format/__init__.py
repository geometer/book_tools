import magic, zipfile
from xml import sax

from fbreader.format.mimetype import Mimetype

from fbreader.format.util import list_zip_file_infos
from fbreader.format.epub import EPub
from fbreader.format.fb2 import FB2, FB2Zip
#from fbreader.format.pdf import PDF
#from fbreader.format.msword import MSWord
from fbreader.format.mobi import Mobipocket
#from fbreader.format.rtf import RTF
#from fbreader.format.djvu import DjVu
#from fbreader.format.dummy import Dummy

__detector = magic.open(magic.MAGIC_MIME_TYPE)
__detector.load()

def detect_mime(filename):
    FB2_ROOT = 'FictionBook'

    mime = __detector.file(filename)

    try:
        if mime == Mimetype.XML:
            if FB2_ROOT == __xml_root_tag(filename):
                return Mimetype.FB2
        elif mime == Mimetype.ZIP:
            with zipfile.ZipFile(filename) as zip_file:
                if not zip_file.testzip():
                    infolist = list_zip_file_infos(zip_file)
                    if len(infolist) == 1:
                        if FB2_ROOT == __xml_root_tag(zip_file.open(infolist[0])):
                            return Mimetype.FB2_ZIP
                    try:
                        with zip_file.open('mimetype') as mimetype_file:
                            if mimetype_file.read(30).rstrip('\n\r') == Mimetype.EPUB:
                                return Mimetype.EPUB
                    except:
                        pass
        elif mime == Mimetype.OCTET_STREAM:
            with open(filename, 'rb') as f:
                if f.read(68)[60:] == 'BOOKMOBI':
                    return Mimetype.MOBI
    except:
        pass
        
    return mime

def create_bookfile(path, original_filename):
    mimetype = detect_mime(path)
    if mimetype == Mimetype.EPUB:
        return EPub(path, original_filename)
    elif mimetype == Mimetype.FB2:
        return FB2(path, original_filename)
    elif mimetype == Mimetype.FB2_ZIP:
        return FB2Zip(path, original_filename)
    elif mimetype == Mimetype.PDF:
        return PDF(path, original_filename)
    elif mimetype == Mimetype.MSWORD:
        return MSWord(path, original_filename)
    elif mimetype == Mimetype.MOBI:
        return Mobipocket(path, original_filename)
    elif mimetype == Mimetype.RTF:
        return RTF(path, original_filename)
    elif mimetype == Mimetype.DJVU:
        return DjVu(path, original_filename)
    elif mimetype in [Mimetype.TEXT]:
        return Dummy(path, original_filename, mimetype)
    else:
        raise Exception('File type \'%s\' is not supported, sorry' % mimetype)

def __xml_root_tag(filename):
    class XMLRootFound(Exception):
        def __init__(self, name):
            self.name = name

    class RootTagFinder(sax.handler.ContentHandler):
        def startElement(self, name, attributes):
            raise XMLRootFound(name)

    try:
        sax.parse(filename, RootTagFinder())
    except XMLRootFound, e:
        return e.name
    return None

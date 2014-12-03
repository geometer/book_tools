import os, shutil
from tempfile import mkdtemp

from pymobi.mobi import BookMobi

from fbreader.format.bookfile import BookFile
from fbreader.format.mimetype import Mimetype

class Mobipocket(BookFile):
    def __init__(self, path, original_filename):
        BookFile.__init__(self, path, original_filename, Mimetype.MOBI)
        bm = BookMobi(path)
        self._encryption_method = bm['encryption']
        self.__set_title__(bm['title'])
        self.__add_author__(bm['author'])
        if bm['subject']:
            for tag in bm['subject']:
                self.__add_tag__(tag)
        self.description = bm['description']

    def __exit__(self, kind, value, traceback):
        pass

    def get_encryption_info(self):
        return {'method': self._encryption_method} if self._encryption_method != 'no encryption' else {}

    def extract_cover_internal(self, working_dir):
        tmp_dir = mkdtemp(dir=working_dir)
        BookMobi(self.path).unpackMobi(tmp_dir + '/bookmobi')
        try:
            if os.path.isfile(tmp_dir + '/bookmobi_cover.jpg'):
                shutil.copy(tmp_dir + '/bookmobi_cover.jpg', working_dir)
                return ('bookmobi_cover.jpg', False)
            else:
                return (None, False)
        finally:
            shutil.rmtree(tmp_dir)

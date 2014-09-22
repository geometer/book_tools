import os, re
from abc import abstractmethod, ABCMeta

class BookFile(object):
    __metaclass__ = ABCMeta

    def __init__(self, path, original_filename, mimetype):
        self.path = path
        self.mimetype = mimetype
        self.original_filename = original_filename
        self.title = original_filename
        self.description = None
        self.authors = []
        self.tags = []
        self.series_info = None
        self.language_code = None
        self.issues = []

    def __enter__(self):
        return self

    @abstractmethod
    def __exit__(self, kind, value, traceback):
        pass

    def extract_cover(self, working_dir):
        cover, minified = self.extract_cover_internal(working_dir)
        return cover

    def extract_cover_internal(self, working_dir):
        return (None, False)

    @staticmethod
    def __is_text(text):
        return isinstance(text, str) or isinstance(text, unicode)

    def __set_title__(self, title):
        if title and BookFile.__is_text(title):
            title = title.strip()
            if title:
                self.title = title

    def __add_author__(self, name, sortkey=None):
        if not name or not BookFile.__is_text(name):
            return
        name = BookFile.__normalise_string__(name)
        if not name:
            return
        if sortkey:
            sortkey = sortkey.strip()
        if not sortkey:
            sortkey = name.split()[-1]
        sortkey = BookFile.__normalise_string__(sortkey).lower()
        self.authors.append({'name': name, 'sortkey': sortkey})

    def __add_tag__(self, text):
        if text and BookFile.__is_text(text):
            text = text.strip()
            if text:
                self.tags.append(text)

    @staticmethod
    def __normalise_string__(text):
        if text is None:
            return None
        return re.sub(r'\s+', ' ', text.strip())

    def get_encryption_info(self):
        return {}

    def repair(self, working_dir):
        pass

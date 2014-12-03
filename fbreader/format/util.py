def list_zip_file_infos(zipfile):
    return [info for info in zipfile.infolist() if not info.filename.endswith('/')]

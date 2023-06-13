import logging as log
import os
from datamaker.src.tools import get_list_of_folder, extract_url_zip

RESOURCE_DIR = 'datamaker/resources/'


TEMPLATE_URL = 'https://github.com/SciCrunch/sparc-curation/releases/download/dataset-template-{version}/DatasetTemplate-{version}.zip'

class Schema:
    def __init__(self):
        pass

    @staticmethod
    def download_schema(version:str, release_url:str):
        """
        This function dowloads and extract dataset-template from SciCrunch / sparc-curration
        : version: is the release version, e.g. 1.2.3, 2.0.0, 2.1.0
        : releare_url: is a url to a dataset-template release in from SciCrunch / sparc-curration \
                       for example: https://github.com/SciCrunch/sparc-curation/releases/download/dataset-template-2.1.0/DatasetTemplate-2.1.0.zip
        """
        if not release_url.startswith('https'):
            log.error(f'Invalid release dataset-template url')
            return

        folders = get_list_of_folder(RESOURCE_DIR)
        if version in folders:
            log.warning(f'The template and schema version {version} is available')
            return
        
        extract_url_zip(release_url, os.path.join(RESOURCE_DIR, version))

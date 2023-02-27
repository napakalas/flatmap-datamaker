#===============================================================================
#
#  Flatmap viewer and annotation tools
#
#  Copyright (c) 2020-2021  David Brooks
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#===============================================================================

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import mimetypes

import pandas

import openpyxl
import requests
from io import BytesIO

#===============================================================================

class SourceError(Exception):
    pass

#===============================================================================

METADATA_VERSION = '1.2.3'

#===============================================================================

ADDTIONAL_LINKS = [
    {
        'url': 'https://github.com/dbrnz/flatmap-maker',
        'description': 'Generate flatmaps for viewing'
    },
    {
        'url': 'https://github.com/dbrnz/flatmap-server',
        'description': 'Server for generated flatmaps'
    },
    {
        'url': 'https://github.com/ABI-Software/flatmap-viewer',
        'description': 'View generated flatmaps'
    },
]

#===============================================================================

TEMPLATE_LINK = 'https://github.com/SciCrunch/sparc-curation/blob/master/resources/DatasetTemplate/dataset_description.xlsx?raw=true'

#===============================================================================

from datamaker.manifest import Manifest, pathlib_path

#===============================================================================

class DatasetDescription:
    def __init__(self, workspace, description, uuid, is_latest=True, version=None):
        self.__workbook = self.__load_template_workbook(is_latest=is_latest, version=version)
        
        self.__source_dir = workspace.path
        with open(self.__source_dir.joinpath(description)) as fd:
            description = json.loads(fd.read())
        
        self.__write_cell('type', 'simulation')
        self.__write_cell('title', description['title'])
        self.__write_cell('keywords', description['keywords'])
        self.__write_cell('contributor name', [c['name'] if 'name' in c else '' for c in description['contributors']])
        self.__write_cell('contributor orcid', [c['orcid'] if 'orcid' in c else '' for c in description['contributors']])
        self.__write_cell('contributor affiliation', [c['affiliation'] if 'affiliation' in c else '' for c in description['contributors']])
        self.__write_cell('contributor role', [c['role'] if 'role' in c else '' for c in description['contributors']])
        if uuid != None:
            self.__write_cell('identifier', str(uuid))
        self.__write_cell('identifier type', 'uuid')
        self.__write_cell('funding', description['funding'])
        self.__write_cell('identifier description', ['', ''])
        self.__write_cell('relation type', ['', ''])
        
    def __load_template_workbook(self, is_latest=True, version=None):
        """
        : is_latest: the default is True, if None, should specify the version
        : version: the default is None for the latest version
        """
        headers = {'Content-Type': 'application/xlsx'}
        template = requests.request('GET', TEMPLATE_LINK, headers=headers)
        workbook = openpyxl.load_workbook(BytesIO(template.content))
        return workbook
        
    def __write_cell(self, key, values):
        worksheet = self.__workbook.worksheets[0]
        data_pos = 3
        if not isinstance(values, list):
            values = [values]
        for row in worksheet.rows:
            if row[0].value.lower().strip() == key:
                for pos in range(len(values)):
                    row[pos+data_pos].value = str(values[pos])

    def write(self):
        sds_description = (self.__source_dir / 'dataset_description.xlsx').resolve()
        self.__workbook.save(sds_description)
        return sds_description

#===============================================================================

@dataclass
class DatasetFile:
    filename: str
    fullpath: Path
    timestamp: datetime
    description: str
    file_type: str

#===============================================================================

class DirectoryManifest:
    COLUMNS = (
        'filename',
        'timestamp',
        'description',
        'file type',
    )

    def __init__(self, workspace, metadata_columns=None):
        self.__workspace = workspace
        self.__path = self.__workspace.path
        self.__metadata_columns = metadata_columns if metadata_columns is not None else []
        self.__files = []
        self.__file_records = []
        self.__manifest = None

    @property
    def files(self):
        return self.__files

    @property
    def manifest(self):
        return self.__manifest

    def add_file(self, filename, description, **metadata):
        fullpath = (self.__path / filename).resolve()
        if not fullpath.exists():
            raise SourceError(f'Missing file: {fullpath}')
        try:
            relative_path = fullpath.relative_to(self.__path)
        except ValueError:
            raise SourceError(f'Manifest file paths must be relative: {fullpath}') from None
        file_type = mimetypes.guess_type(fullpath, strict=False)[0]
        if file_type is None:
            file_type = fullpath.suffix
        dataset_file = DatasetFile(str(relative_path),
                                   fullpath,
                                   self.__workspace.last_commit_time(relative_path),
                                   description,
                                   file_type)
        self.__files.append(dataset_file)
        record = [
            dataset_file.filename,
            dataset_file.timestamp.isoformat(),
            dataset_file.description,
            dataset_file.file_type
        ]
        for column_name in self.__metadata_columns:
            record.append(metadata.get(column_name))
        self.__file_records.append(record)

    def write(self):
        self.__manifest = (self.__path / 'manifest.xlsx').resolve()
        pandas.DataFrame(
            self.__file_records,
            columns = self.COLUMNS + tuple(self.__metadata_columns)
        ).to_excel(self.__manifest)

#===============================================================================

class FlatmapSource(Manifest):
    def __init__(self, workspace, manifest_file):
        Manifest.__init__(self, f'{workspace.path}/{manifest_file}', ignore_git=False)

        # this lines should be modified
        if not 'description' in self._Manifest__manifest:
            raise SourceError('Flatmap manifest must specify a description')
        description = self._Manifest__manifest['description']
        # until this point
        dataset_description = DatasetDescription(workspace, description, self.uuid)
        self.__dataset_description = dataset_description.write()

        species = self.models
        metadata = {'species': species} if species is not None else {}
        
        directory_manifest = DirectoryManifest(workspace)
        directory_manifest.add_file(workspace.path.joinpath(description), 'flatmap dataset description', **metadata)
        directory_manifest.add_file(pathlib_path(self.anatomical_map), 'flatmap annatomical map', **metadata)
        directory_manifest.add_file(pathlib_path(self.properties), 'flatmap properties', **metadata)
        for connectivity_file in self.connectivity:
            directory_manifest.add_file(pathlib_path(connectivity_file), 'flatmap connectivity', **metadata)
        for source in self.sources:
            if source['href'].split(':', 1)[0] not in ['file', 'http', 'https']:
                directory_manifest.add_file(pathlib_path(source['href']), 'flatmap source', **metadata)

        directory_manifest.write()
        self.__dataset_manifests = [ directory_manifest ]

    @property
    def dataset_description(self):
        return self.__dataset_description

    @property
    def dataset_manifests(self):
        return self.__dataset_manifests

    @property
    def manifest(self):
        return self.__manifest

#===============================================================================

"""
``--dataset`` option to mapmaker specifies directory in which to put files.

In this directory::

    $ makedir -p files/primary
    $ cp MAPSOURCES files/primary

    directory_manifest = DirectoryManifest('.')
    FOREACH MAPSOURCE:
        directory_manifest.add_file('files/primary/MAPSOURCE', 'MAPSOURCE description')
    directory_manifest.write()

    dataset_description = DatasetDescription('.')
      .
      .
      .
    dataset_description.write()


"""

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

class DatasetDescription:
    COLUMNS = (
        'Metadata element',
        'Description',
        'Example',
        'Value',
    )
    ROW_ELEMENTS = (
        'Name',
        'Description',
        'Keywords',
        'Contributors',
        'Contributor ORCID ID',
        'Contributor Affiliation',
        'Contributor Role',
        'Is Contact Person',
        'Acknowledgements',
        'Funding',
        'Originating Article DOI',
        'Protocol URL or DOI',
        'Additional Links',
        'Link Description',
        'Number of subjects',
        'Number of samples',
        'Completeness of data set',
        'Parent dataset ID',
        'Title for complete data set',
        'Metadata Version DO NOT CHANGE',
    )

    def __init__(self, workspace, description):
        self.__source_dir = workspace.path
        with open(self.__source_dir.joinpath(description)) as fd:
            description = json.loads(fd.read())
        values = defaultdict(list)
        values['Metadata Version DO NOT CHANGE'] = METADATA_VERSION
        values['Name'] = description['title']
        values['Title for complete data set'] = description['title']
        values['Description'] = description['description']
        values['Keywords'] = [ kw for kw in description.get('keywords', []) ]
        for contributor in description['contributors']:
            values['Contributors'].append(contributor['name'])
            values['Contributor ORCID ID'].append(contributor.get('orcid'))
            values['Contributor Affiliation'].append(contributor['affiliation'])
            values['Contributor Role'].append(contributor['role'])
            values['Is Contact Person'].append(contributor.get('contact', 'Yes'))
        values['Funding'] = description.get('funding')
        for link in ADDTIONAL_LINKS:
            values['Additional Links'].append(link['url'])
            values['Link Description'].append(link['description'])
        values['Number of subjects'] = 0
        values['Number of samples'] = 0
        self.__rows = []
        value_size = 1
        for element in self.ROW_ELEMENTS:
            value = values.get(element)
            if not isinstance(value, list):
                value = [ value ]
            if len(value) > value_size:
                value_size = len(value)
            self.__rows.append([ element, '', '' ] + value)
        self.__columns = self.COLUMNS + tuple(f'Value {n+2}' for n in range(value_size-1))

    def write(self):
        sds_description = (self.__source_dir / 'dataset_description.xlsx').resolve()
        pandas.DataFrame(self.__rows, columns=self.__columns).fillna(value='').to_excel(sds_description)
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

class FlatmapSource:
    def __init__(self, workspace, manifest_file):
        source_dir = workspace.path
        with open(source_dir.joinpath(manifest_file), 'r') as fd:
            manifest = json.loads(fd.read())

        if not 'description' in manifest:
            raise SourceError('Flatmap manifest must specify a description')
        dataset_description = DatasetDescription(workspace, manifest['description'])
        self.__dataset_description = dataset_description.write()

        species = manifest.get('models')
        metadata = {'species': species} if species is not None else {}

        directory_manifest = DirectoryManifest(workspace)
        directory_manifest.add_file(
            source_dir.joinpath(manifest['description']), 'flatmap dataset description', **metadata)
        directory_manifest.add_file(
            source_dir.joinpath(manifest.get('anatomicalMap')), 'flatmap annatomical map', **metadata)
        directory_manifest.add_file(
            source_dir.joinpath(manifest.get('properties')), 'flatmap properties', **metadata)
        for connectivity_file in manifest.get('connectivity', []):
            directory_manifest.add_file(
                source_dir.joinpath(connectivity_file), 'flatmap connectivity', **metadata)
        for source in manifest.get('sources', []):
            if source['href'].split(':', 1)[0] not in ['file', 'http', 'https']:
                directory_manifest.add_file(
                    source_dir.joinpath(source['href']), 'flatmap source', **metadata)

        directory_manifest.write()
        self.__dataset_manifests = [ directory_manifest ]

    @property
    def dataset_description(self):
        return self.__dataset_description

    @property
    def dataset_manifests(self):
        return self.__dataset_manifests


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

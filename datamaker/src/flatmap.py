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

MAPPING_URL = "https://github.com/napakalas/flatmap-datamaker/blob/main/datamaker/resources/data_mapping.json?raw=true"

#===============================================================================

"""Need to modify this import for integration to map-maker"""
from datamaker.src.manifest import Manifest
# from mapmaker.maker import Manifest

from datamaker.src.manifest import pathlib_path
#from mapmaker.utils import pathlib_path

#===============================================================================

class VersionMapping:
    def __init__(self):
        headers = {'Content-Type': 'application/json'}
        results = requests.request('GET', MAPPING_URL, headers=headers)
        self.__mappings = json.loads(results.content)

    @property
    def available_versions(self):
        return [v['version'] for v in self.__mappings]

    def get_mapping(self, other_params):
        """
        : other_params: is a dictionary containing other data such as uuid and version
        """
        version = other_params.get('version', None)
        mapping = None
        if version == None:
            mapping = self.__mappings[0]
        else:
            for v in self.__mappings:
                if v['version'] == version:
                    mapping = v
        if mapping == None:
            raise SourceError('Dataset-Description version-{} is not available'.format(version))
        for m in mapping['mapping']:
            if len(m[1])> 0:
                param = m[1][-1]
                if param in other_params:
                    m[2] = other_params[param]
        return mapping

#===============================================================================

class DatasetDescription:
    def __init__(self, workspace, description_file, other_params):
        """
        : other_params: is a dictionary containing other data including uuid and version
        """
        self.__mapping = VersionMapping().get_mapping(other_params)
        self.__workbook = self.__load_template_workbook(self.__mapping['template_url'])
        
        self.__source_dir = workspace.generated_path

        try:
            with open(workspace.path.joinpath(description_file), 'r') as fd:
                description = json.loads(fd.read())
        except FileNotFoundError:
            raise FileNotFoundError('Cannot open path: {}'.format(description_file)) from None
        
        for m in self.__mapping['mapping']:
             self.__write_cell(m, description)
        
    def __load_template_workbook(self, template_link):
        """
        : template_link: link to dataset_description.xlsx
        """
        headers = {'Content-Type': 'application/xlsx'}
        template = requests.request('GET', template_link, headers=headers)
        workbook = openpyxl.load_workbook(BytesIO(template.content))
        return workbook
        
    def __write_cell(self, map, description):
        worksheet = self.__workbook.worksheets[0]
        data_pos = self.__mapping.get('data_pos', 3)
        key, dsc, default = map
        values = default if isinstance(default, list) else [default]

        if len(dsc) == 1:
            if dsc[0] in description:
                values = description[dsc[-1]] if isinstance(description[dsc[-1]], list) else [description[dsc[-1]]]
        elif len(dsc) > 1:
            tmp_values = description
            for d in dsc:
                if isinstance(tmp_values, dict):
                    tmp_values = tmp_values.get(d, {})
                elif isinstance(tmp_values, list):
                    tmp_values = [val.get(d, '') for val in tmp_values]
            
            if len(tmp_values) > 0:
                values = tmp_values if isinstance(tmp_values, list) else [tmp_values]

        for row in worksheet.rows:
            if row[0].value == None:
                break
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
        self.__generated_path = self.__workspace.generated_path
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
        self.__manifest = (self.__generated_path / 'manifest.xlsx').resolve()
        pandas.DataFrame(
            self.__file_records,
            columns = self.COLUMNS + tuple(self.__metadata_columns)
        ).to_excel(self.__manifest)

#===============================================================================

class FlatmapSource:
    def __init__(self, workspace, manifest, description, version, id, id_type):
        """
        : workspace: a Workspace instance
        : manifest: manifest object of Manifest class 
        : version: dataset_description version
        """
        
        # checking description file profided by Flatmap manifest
        if len(manifest.description) > 0 :
            description = manifest.description
        if description == None:
            raise SourceError('Flatmap manifest must specify a description file')

        # creating dataset_description.xlsx
        other_params = {'version':version, 'id':id, 'id_type':id_type} # version:
        if (id_type == None or id_type.upper() == 'URL') and id == None:
            other_params['id_type'] = 'URL'
            other_params['id'] = workspace.workspace_url()
        elif id_type.upper() == 'UUID' and id == None:
            other_params['id_type'] = 'UUID'
            other_params['id'] = manifest.uuid        
        dataset_description = DatasetDescription(workspace, description, other_params)
        self.__dataset_description = dataset_description.write()

        # creating dataset manifest.xlsx
        species = manifest.models
        metadata = {'species': species} if species is not None else {}
        
        # adding files to be store in primary directory
        directory_manifest = DirectoryManifest(workspace)
        # directory_manifest.add_file(workspace.path.joinpath(manifest.description), 'flatmap dataset description', **metadata)
        if manifest.anatomical_map != None:
            directory_manifest.add_file(pathlib_path(manifest.anatomical_map), 'flatmap annatomical map', **metadata)
        if manifest.properties != None:
            directory_manifest.add_file(pathlib_path(manifest.properties), 'flatmap properties', **metadata)
        if manifest.connectivity_terms != None:
            directory_manifest.add_file(pathlib_path(manifest.connectivity_terms), 'flatmap connectivity terms', **metadata)
        for connectivity_file in manifest.connectivity:
            directory_manifest.add_file(pathlib_path(connectivity_file), 'flatmap connectivity', **metadata)
        for source in manifest.sources:
            if source['href'].split(':', 1)[0] in ['file']:
                directory_manifest.add_file(pathlib_path(source['href']), 'flatmap source', **metadata)
        # adding manifest.json to directory_manifest
        directory_manifest.add_file(pathlib_path(manifest.url), 'manifest to bult map', **metadata)

        # for source in manifest.sources:
        #     if source['href'].split(':', 1)[0] not in ['file', 'http', 'https']:
        #         directory_manifest.add_file(pathlib_path(source['href']), 'flatmap source', **metadata)

        directory_manifest.write()
        self.__dataset_manifests = [directory_manifest]

    @property
    def dataset_description(self):
        return self.__dataset_description

    @property
    def dataset_manifests(self):
        return self.__dataset_manifests

    @property
    def dataset_source(self):
        for dataset_manifest in self.__dataset_manifests:
            for file in dataset_manifest.files:
                if file.filename.endswith('.pptx') or file.filename.endswith('.svg'):
                    return file.fullpath
        return None

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

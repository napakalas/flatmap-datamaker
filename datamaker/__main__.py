#===============================================================================
#
#  Flatmap viewer and annotation tools
#
#  Copyright (c) 2019  David Brooks
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

import argparse
import shutil
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

#===============================================================================

from datamaker.flatmap import FlatmapSource, SourceError
from datamaker.workspace import Workspace

#===============================================================================

def mapdatamaker(workspace, commit, manifest_file, dataset):
    workspace = Workspace(workspace, commit)
    source = FlatmapSource(workspace, manifest_file)
    dataset_archive = ZipFile(dataset, mode='w', compression=ZIP_DEFLATED)
    for dataset_manifest in source.dataset_manifests:
        for file in dataset_manifest.files:
            zinfo = ZipInfo.from_file(str(file.fullpath), arcname=f'files/primary/{file.filename}')
            zinfo.compress_type = ZIP_DEFLATED
            timestamp = file.timestamp
            zinfo.date_time = (timestamp.year, timestamp.month, timestamp.day,
                               timestamp.hour, timestamp.minute, timestamp.second)
            with open(file.fullpath, "rb") as src, dataset_archive.open(zinfo, 'w') as dest:
                shutil.copyfileobj(src, dest, 1024*8)
        manifest = dataset_manifest.manifest
        dataset_archive.write(str(manifest), arcname=f'files/primary/{manifest.name}')
    dataset_description = source.dataset_description
    dataset_archive.write(str(dataset_description), arcname=f'files/{dataset_description.name}')
    dataset_archive.close()
    workspace.close()

#===============================================================================

def main():
    import sys

    parser = argparse.ArgumentParser(description="Create a SPARC Dataset of a flatmap's sources on PMR")
    parser.add_argument('workspace', metavar='WORKSPACE', help='URL of a PMR workspace containing a flatmap manifest')
    parser.add_argument('commit', metavar='COMMIT', help='SHA of workspace commit to use for dataset')
    parser.add_argument('manifest', metavar='MANIFEST', help='name of flatmap manifest in workspace')
    parser.add_argument('dataset', metavar='DATASET', help='full name for resulting dataset')

    try:
        args = parser.parse_args()
        mapdatamaker(args.workspace, args.commit, args.manifest, args.dataset)
    except SourceError as error:
        sys.stderr.write(f'{error}\n')
        sys.exit(1)
    sys.exit(0)

#===============================================================================

if __name__ == '__main__':
    main()

#===============================================================================

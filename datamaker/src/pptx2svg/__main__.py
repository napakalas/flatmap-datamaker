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

import json
import os
from pathlib import Path
from urllib.parse import urljoin

#===============================================================================

from datamaker.src.pptx2svg.pptx2svg import SvgExtractor

#===============================================================================

if __name__ == '__main__':
    import argparse
    import pathlib
    import sys

    parser = argparse.ArgumentParser(description='Convert Powerpoint slides to SVG.')

    parser.add_argument('-d', '--debug', action='store_true', help='save DrawML to aid with debugging')
    parser.add_argument('-q', '--quiet', action='store_true', help='do not show progress bar')
    parser.add_argument('-v', '--version', action='version', version=__version__)

    parser.add_argument('--powerpoint', metavar='POWERPOINT_FILE',
                        help='the Powerpoint file to convert')
    parser.add_argument('--map', dest='map_dir', metavar='MAP_DIR',
                        help='directory containing a flatmap manifest specifying sources')

    args = parser.parse_args()

    if args.powerpoint is None and args.map_dir is None:
        sys.exit('A map directory or Powerpoint file must be specified')
    elif args.powerpoint is not None and args.map_dir is not None:
        sys.exit('Cannot specify both a map directory and a Powerpoint file')

    if args.map_dir:
        manifest_file = os.path.join(args.map_dir, 'manifest.json')
        with open(manifest_file, 'rb') as fp:
            manifest = json.loads(fp.read())
        for source in manifest['sources']:
            if source['kind'] == 'slides':
                manifest_path = pathlib.Path(manifest_file).absolute().as_posix()
                args.powerpoint = urljoin(manifest_path, source['href'])
                break
        if args.powerpoint is None:
            sys.exit('No Powerpoint file specified in manifest')
        args.output_dir = args.map_dir
    else:
        manifest = { 'sources': [] }
        args.output_dir = Path(args.powerpoint).parent.as_posix()

    extractor = SvgExtractor(args)
    extractor.slides_to_svg()

    # Update an existing manifest
    extractor.update_manifest(manifest)
    manifest_temp_file = os.path.join(args.output_dir, 'manifest.temp')
    with open(manifest_temp_file, 'w') as output:
        output.write(json.dumps(manifest, indent=4))
    manifest_file = os.path.join(args.output_dir, 'manifest.json')
    os.rename(manifest_temp_file, manifest_file)
    print('Manifest saved as `{}`'.format(manifest_file))

#===============================================================================


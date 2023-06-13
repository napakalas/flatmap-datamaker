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

#===============================================================================

from datamaker.src.flatmap import SourceError
from datamaker.src.dataset import Dataset

#===============================================================================

def main():
    import sys

    parser = argparse.ArgumentParser(description="Create a SPARC Dataset of a flatmap's sources on PMR")

    parser.add_argument('--workspace', metavar='WORKSPACE', required=True,
                        help='URL of a PMR workspace containing a flatmap manifest')
    parser.add_argument('--commit', metavar='COMMIT', 
                        help='SHA of workspace commit to use for dataset')
    parser.add_argument('--manifest', metavar='MANIFEST', required=True,
                        help='name of flatmap manifest in workspace')
    parser.add_argument('--derivative', metavar='DERIVATIVE', 
                        help='URL of a PMR workspace containing a generated flatmap')
    parser.add_argument('--description', metavar='description', 
                        help='name of flatmap description in workspace')
    parser.add_argument('--dataset', metavar='DATASET', required=True,
                        help='full name and path for resulting dataset')
    parser.add_argument('--version', metavar='VERSION', 
                        help='version of dataset_description, optional -> empty will be the latest version', nargs='?', const=None)
    parser.add_argument('--ignore-git', dest='ignore_git', action='store_true', 
                        help="Don't check that sources are committed into git")
    parser.add_argument('--id', metavar='ID',
                        help="an ID used to identify the dataset")
    parser.add_argument('--id-type', dest='id_type', 
                        help="the ID type, e.g. URL and URI")
    parser.add_argument('--log-file', dest='log_file', 
                        help="a log file storing map generation process")    
    

    try:
        opts = vars(parser.parse_args())
        dataset = Dataset(workspace_path = opts['workspace'], 
                          manifest_file = opts['manifest'], 
                          output = opts['dataset'], 
                          commit = opts['commit'], 
                          derivative = opts['derivative'], 
                          description = opts['description'],
                          version = opts['version'], 
                          ignone_git = opts['ignore_git'], 
                          id = opts['id'], 
                          id_type = opts['id_type'],
                          log_file = opts['log_file'])
        dataset.save_archive()
        dataset.close()
        
        # mapdatamaker(args.workspace, args.commit, args.manifest, args.dataset, args.version, args.ig)
    except SourceError as error:
        sys.stderr.write(f'{error}\n')
        sys.exit(1)
    sys.exit(0)

#===============================================================================

if __name__ == '__main__':
    main()

#===============================================================================

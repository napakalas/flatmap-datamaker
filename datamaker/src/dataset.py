import shutil
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import os
from datetime import datetime
import mimetypes
import pandas as pd
import io
from cairosvg import svg2png

#===============================================================================

from datamaker.src.flatmap import FlatmapSource
from datamaker.src.workspace import Workspace
from datamaker.src.pptx2svg.pptx2svg import SvgExtractor
from datamaker.src.manifest import FilePathError

#===============================================================================

from datamaker.src.tools import get_mapmaker_version, get_mapknowledge_version, get_sckan_version

#===============================================================================

# for implementation this line probably is not necessary
# when combined with flatmap_maker, maninfest object should use the available
#    object, to manage uuid consistency
from datamaker.src.manifest import Manifest
# from mapmaker.maker import Manifest

#===============================================================================

class Dataset:
    """
    A class used to represent dataset with given maps data
    """

    def __init__(self, workspace_path, manifest_file, output, commit=None, derivative=None, description=None, version=None, ignone_git=True, id=None, id_type=None, log_file=None):
        """
        : workspace_path:is the path or URL to the flatmap.
        : manifest_file: is the name of manifest files.
        : description:   is the name of description file
        : output:        is the pat of the generated dataset
        : derivative:    is a path to generated flatmap by mapmaker.
        : commit:        is the commit versing. Default to None.
        : version:       is the the version of dataset_description, i.e. 1.2.3 and 2.1.0. 
                         None value will generate the latest one.
        : ignore_git:    is specifying wether considering git or not. Default to True.
        : id:            is the id of the dataset. Default to git URL.
        : id_type:       is the type of id. Default to URL.
        """
        self.__workspace = Workspace(workspace_path, commit, ignone_git)
        self.__manifest = Manifest(f'{self.__workspace.path}/{manifest_file}', ignore_git=ignone_git)
        self.__derivative_path = derivative
        self.__source = FlatmapSource(self.__workspace, self.__manifest, description, version, id=id, id_type=id_type)
        self.__dataset_output = output
        self.__log_file = log_file

    def save_archive(self):
        dataset_archive = ZipFile(self.__dataset_output, mode='w', compression=ZIP_DEFLATED)

        # copy primary data
        self.__copy_primary(dataset_archive)
        
        # this one save derivatives
        self.__copy_derivative(dataset_archive)
        
        # adding dataset_description
        dataset_description = self.__source.dataset_description
        dataset_archive.write(str(dataset_description), arcname=f'files/{dataset_description.name}')

        # create and save banner file
        self.__create_banner(dataset_archive)

        # create and save proper readme file, generated for dataset_description
        # dont forget to add SCKAN and MapMaker versions
        # self.__add_readme(dataset_a rchive)

        # close archive
        dataset_archive.close()

    def __copy_primary(self, archive):
        for dataset_manifest in self.__source.dataset_manifests:
            for file in dataset_manifest.files:
                zinfo = ZipInfo.from_file(str(file.fullpath), arcname=f'files/primary/{file.filename}')
                zinfo.compress_type = ZIP_DEFLATED
                timestamp = file.timestamp
                zinfo.date_time = (timestamp.year, timestamp.month, timestamp.day,
                                timestamp.hour, timestamp.minute, timestamp.second)
                with open(file.fullpath, "rb") as src, archive.open(zinfo, 'w') as dest:
                    shutil.copyfileobj(src, dest, 1024*8)
            manifest = dataset_manifest.manifest
            archive.write(str(manifest), arcname=f'files/primary/{manifest.name}')
        
    def __copy_derivative(self, archive):
        if self.__derivative_path != None:
            derivative_files = []
            for root, dirs, files in os.walk(self.__derivative_path):
                for filename in files:
                    if filename.startswith('.'):
                        continue
                    # Get the full path of the file
                    fullpath = os.path.join(root, filename)
                    zinfo = ZipInfo.from_file(fullpath, arcname=f'files/derivative/{filename}')
                    zinfo.compress_type = ZIP_DEFLATED
                    timestamp = datetime.fromtimestamp(os.path.getmtime(fullpath))
                    zinfo.date_time = (timestamp.year, timestamp.month, timestamp.day,
                                    timestamp.hour, timestamp.minute, timestamp.second)
                    with open(fullpath, "rb") as src, archive.open(zinfo, 'w') as dest:
                        shutil.copyfileobj(src, dest, 1024*8)
                    file_type = mimetypes.guess_type(fullpath, strict=False)[0]
                    if file_type is None:
                        file_type = fullpath.split('.')[-1]
                    derivative_files += [[filename, timestamp.isoformat(), 'derivative file loaded by map server', file_type]]
            if len(derivative_files) > 0:
                columns = ['filename', 'timestamp', 'description', 'file type',]
                excel_file = io.BytesIO()
                df = pd.DataFrame(derivative_files, columns=columns)
                writer = pd.ExcelWriter(excel_file, engine='xlsxwriter')
                df.to_excel(writer, sheet_name='Sheet1', index=False)
                writer.close()
                excel_file.seek(0)
                archive.writestr('files/derivative/manifest.xlsx', excel_file.getvalue())

    def __add_readme(self, archive):
        readme = []

        readme += ['## INFO', get_sckan_version()]
        if self.__log_file != None:
            readme += [get_mapmaker_version(self.__log_file), get_mapknowledge_version(self.__log_file)]

        # print(self.__source.dataset_description.workbook())
        

        
        print(readme)
        # print(get_mapmaker_version)
        # print(get_mapknowledge_version)

    def __create_banner(self, archive):
        image_path = str(self.__source.dataset_source)
        if image_path.endswith('.pptx'):
            options = type('', (object,),{
                'powerpoint' : image_path,
                'debug' : False,
                'quiet' : False,
                'output_dir' : self.__workspace.generated_path
            })
            extractor = SvgExtractor(options)
            extractor.slides_to_svg()
            image_path = os.path.join(options.output_dir, list(extractor.saved_svg.values())[0])
        
        if image_path.endswith('.svg'):
            png_data = svg2png(url=image_path)
            archive.writestr('files/banner.png', png_data)
        else:
            raise FilePathError('Not valid svg or pptx file') 

    def close(self):
        self.__workspace.close()
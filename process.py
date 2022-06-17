import os
import shutil
import traceback
import tempfile
import argparse
from colorama import init, Fore, Style
from owslib.wmts import WebMapTileService

# fix colorama colors in windows console
init(convert=True)

tmp_folder = f'{tempfile.gettempdir()}\\wmts-downloader'
output_folder = 'output'

zoom = 15
format = 'image/png'
url = ''
proj = 'EPSG:3857'
limit_requests = 1000

parser = argparse.ArgumentParser(description='Script to download images from a WMTS service')
parser.add_argument('url', type=str, metavar='WMTS server url', help='Server url (default: %(default)s)')
parser.add_argument('--layer', type=str, metavar='Layer name', help='Layer name (default: %(default)s)')
parser.add_argument('--format', type=str, metavar='Image format', default=format, help='Image format supported by the geoserver (default: %(default)s)')
parser.add_argument('--zoom', type=int, metavar='Zoom level', default=zoom, help='Zoom level. Higher number is more detail, and more images (default: %(default)s)')
parser.add_argument('--proj', type=str, metavar='EPSG projection code', default=proj, help='EPSG projection code existing in the geoserver (default: %(default)s)')
parser.add_argument('--output', type=str, metavar='Output folder', default=output_folder, help='Folder to save the images (default: %(default)s)')
parser.add_argument('--limit', type=int, metavar='Limit requests number', default=limit_requests, help='Limit the requests to avoid overloading the server (default: %(default)s)')
parser.add_argument('--removeold', action='store_true', help='Remove already downloaded files (default: %(default)s)')

args = parser.parse_args()

def init():

    global output_folder

    try:

        print('--> PROCESS STARTED <--')

        print('\t')

        # check if output folder exists
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        if not os.path.exists(tmp_folder):
            os.makedirs(tmp_folder)

        url = args.url
        format = args.format
        zoom = int(args.zoom)
        proj = args.proj
        layer_id = args.layer 
        output_folder = args.output
        limit_requests = args.limit
        remove_old = args.removeold

        download_count = 1
        skip_count = 0 

        print(f'Connecting to server: {url}')

        try:
            wmts = WebMapTileService(url)
        except Exception as error:
            print(f"{Fore.RED}-> Can't connect to server{Style.RESET_ALL}")
            print(f'{Fore.RED}--> PROCESS WAS ABORTED WITH ERRORS <--{Style.RESET_ALL}')
            return

        print(f'{Fore.GREEN}-> Connection successful{Style.RESET_ALL}')
        print(f'-> Title: {wmts.identification.title}')
        print(f'-> Access constraints: {wmts.identification.accessconstraints}')

        contents = wmts.contents

        print('\t')

        for layer in wmts.contents:
            layer = contents[layer]

            if layer.id == layer_id:

                print(f'-> Layer {layer_id} found')

                title = layer.title
                abstract = layer.abstract
                extent = layer.boundingBoxWGS84
                formats = layer.formats

                print(f'--> Title: {title}')
                print(f'--> Abstract: {abstract}')
                print(f'--> Bounding Box WGS84: {extent}')
                print(f'--> Available formats: {formats}')

                tile_matrixs_links = layer.tilematrixsetlinks

                print(f'--> Available tile matrix sets: {layer._tilematrixsets}')

                for tile_matrix_set in tile_matrixs_links:

                    if tile_matrix_set == proj:

                        tile_matrix_link = tile_matrixs_links[tile_matrix_set]

                        tile_matrix = wmts.tilematrixsets[tile_matrix_set].tilematrix

                        for tml in tile_matrix:

                            z = int(tml.split(":")[-1])

                            if z == zoom:
                                limit = tml

                        matrix_limits = tile_matrix_link.tilematrixlimits[limit]

                        # important
                        matrix = tile_matrix[limit]

                        min_row = matrix_limits.mintilerow
                        max_row = matrix_limits.maxtilerow

                        min_col = matrix_limits.mintilecol
                        max_col = matrix_limits.maxtilecol

                        # check if output folder exists
                        output_folder = f'{output_folder}\\{layer_id}\\{proj.replace(":", "-")}\\{zoom}'

                        if remove_old:
                            if os.path.exists(output_folder):
                                print('Removing old files...')
                                shutil.rmtree(output_folder)
                        
                        # create folder if not exists
                        if not os.path.exists(output_folder):
                            os.makedirs(output_folder)

                        print('\t')
                        print('Downloading images...')

                        for row in range(min_row, max_row):

                            for col in range(min_col, max_col):     
                                                      
                                extension = format.split("/")[-1]
                                file_name = f'{layer_id}__{proj.replace(":", "-")}_col-{col}_row-{row}_zoom-{zoom}'

                                # skip already downloaded files
                                if tile_already_exists(file_name, extension):
                                    print(f'--> Skiping tile ({download_count}): Column {col} - Row {row} - Zoom {zoom}')
                                    skip_count += 1
                                    continue

                                print(f'--> Downloading tile ({download_count}): Column {col} - Row {row} - Zoom {zoom}')

                                img = wmts.gettile(
                                    url,
                                    layer=layer_id,
                                    tilematrixset=tile_matrix_set,
                                    tilematrix=limit,
                                    row=row,
                                    column=col,
                                    format=format
                                )

                                write_world_file(file_name, extension, col, row, matrix)
                                
                                write_image(file_name, extension, img)
                                
                                if download_count >= limit_requests:
                                    break

                                download_count += 1
                            else:
                                continue # only executed if the inner loop did NOT break
                            break  # only executed if the inner loop DID break

        if os.path.exists(tmp_folder):
            print(f'->Removing tmp files...')
            shutil.rmtree(tmp_folder)

        print('\t')
        print('--> PROCESS WAS COMPLETED <--')
        print('------------------------------')
        print(f'-> Layer: {layer_id}')
        print(f'-> Format: {format}')
        print(f'-> Projection: {proj}')
        print(f'-> Zoom: {zoom}')

        print('------------------------------')

        if skip_count:
            print(f'-> Skipped images: {skip_count}')

        if download_count:
            print(f'{Fore.GREEN}-> Downloaded files: {download_count}{Style.RESET_ALL}')
        else:
            print(f'{Fore.YELLOW}-> No files downloaded{Style.RESET_ALL}')
        
        print('------------------------------')
        
        total_tiles = (max_row - min_row) * (max_col - min_col)

        print(f'-> Total tiles in layer: {total_tiles}')
        print(f'-> Tiles remaining: {total_tiles - (skip_count + download_count)}')

        print('------------------------------')

    except Exception as error:
        print(f'{Fore.RED}{error}{Style.RESET_ALL}')
        print(traceback.format_exc())



def tile_already_exists(file_name, extension):
    file_path = f'{output_folder}\\{file_name}.{extension}'
    return os.path.exists(file_path)
    

def write_image(file_name, extension, img):
    '''
    Writes images
    '''
    file_path = f'{output_folder}\\{file_name}.{extension}'

    out = open(file_path, 'wb')
    out.write(img.read())
    out.close()


def write_world_file(file_name, extension, col, row, matrix):
    '''
    Writes world file
    https://gdal.org/drivers/raster/wld.html
    https://en.wikipedia.org/wiki/World_file
    '''

    if extension == 'png':
        wf_ext = 'pgw'
    elif extension == 'tiff' or extension == 'tiff':
        wf_ext = 'tfw'
    elif extension == 'jpg' or extension == 'jpeg':
        wf_ext = 'jgw'
    elif extension == 'gif':
        wf_ext = 'gfw'
    else:
        wf_ext = 'wld'

    pixel_size = 0.00028 # Each pixel is assumed to be 0.28mm
    a = matrix.scaledenominator * pixel_size
    e = matrix.scaledenominator * -pixel_size
    left = ((col * matrix.tilewidth + 0.5) * a) + matrix.topleftcorner[0]
    top = ((row * matrix.tileheight + 0.5) * e) + matrix.topleftcorner[1]

    with open(f'{output_folder}\\{file_name}.{wf_ext}', 'w') as f:
        f.write('%f\n%d\n%d\n%f\n%f\n%f' % (a, 0, 0, e, left, top))

init()
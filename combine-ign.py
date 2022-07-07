import os
import json
import glob
import shutil
import tempfile
import rasterio

from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling

from shapely.geometry import box, mapping, shape

import traceback
import geopandas as gpd
from colorama import init, Fore, Style

# fix colorama colors in windows console
init(convert=True)

tmp_folder = f'{tempfile.gettempdir()}\\wmts-downloader'

input_folder = 'output/cartas_50k/EPSG-3857/14'
output_folder = 'output/merged'
gdf_cards = gpd.read_file('cartas.geojson')
crs = None
master_layer_name = None

# json to store progress looping the tiles
json_tmp = 'progress_tmp.json'


def init():
    try:
        global output_folder, collect_path_tiles, crs, master_layer_name

        if not os.path.exists(tmp_folder):
            os.makedirs(tmp_folder)

        print('--> PROCESS STARTED <--')
        print('\t')

        tiles = get_images()
        tiles_count = len(tiles)

        collect_path_tiles = get_json()

        start = collect_path_tiles['count']
        matched_count = collect_path_tiles['matched']

        print(f'Total tiles: {tiles_count}')

        for i in range(start, len(tiles)):

            tile = tiles[i]

            file_name = os.path.basename(tile)
            layer_name = file_name.split('__')[0]

            if not master_layer_name:
                master_layer_name = layer_name

            attributes = file_name.split('_')
            crs = [x for x in attributes if 'EPSG' in x][0].replace(
                '-', ':')

            matched = False

            with rasterio.open(tile, crs=crs) as dst1:
                bounds_image = box(*dst1.bounds)

                for index, carta in gdf_cards.iterrows():
                    id_carta = carta['caracteristica_de_hoja']
                    faja = carta['numero_faja']
                    geom = carta.geometry

                    if bounds_image.intersects(geom):

                        # check bands
                        number_bands = dst1.meta['count']

                        # all tiles must have the same amount of band to be merged
                        if number_bands != 4:

                            band_1 = dst1.read(1)
                            band_2 = dst1.read(2)

                            out_meta = dst1.meta

                            out_meta.update({
                                "count": 4
                            })

                            tile = f'{tmp_folder}/{file_name}'

                            with rasterio.open(f'{tile}', 'w', **out_meta,) as dst2:
                                dst2.write(band_1, 1)
                                dst2.write(band_1, 2)
                                dst2.write(band_1, 3)
                                dst2.write(band_2, 4)

                        exists_id = False

                        for image in collect_path_tiles['images']:
                            if image['id_carta'] == id_carta:
                                exists_id = image
                                break

                        if exists_id:
                            exists_id['tiles'].append(tile)
                        else:
                            collect_path_tiles['images'].append({
                                "path": tile,
                                "faja": faja,
                                "id_carta": id_carta,
                                "geom": mapping(geom),
                                "tiles": [tile]
                            })

                        matched = True

                if matched:
                    matched_count += 1

            if (i+1) % 100 == 0:
                print(
                    f'{Fore.GREEN}-> Tiles matched: {matched_count}/{(i+1)}{Style.RESET_ALL}')
                collect_path_tiles['count'] = i
                collect_path_tiles['matched'] = matched_count
                write_json(collect_path_tiles)

        print('-> Starting conversion')

        images_len = len(collect_path_tiles['images'])

        print(f'-> {images_len} images to convert')

        for index in range(images_len):

            tiles_collected = collect_path_tiles['images'][index]

            faja = tiles_collected['faja']
            geom = shape(tiles_collected['geom'])
            tiles = tiles_collected['tiles']
            id_carta = tiles_collected['id_carta']

            print(f'-> Conversion Nº {index+1} - {id_carta}')

            output_folder_layer = f'{output_folder}/{master_layer_name}'

            output_folder_layer_crs = f'{output_folder_layer}/{crs.replace(":", "-")}'

            if not os.path.exists(output_folder_layer_crs):
                os.makedirs(output_folder_layer_crs)

            file_tmp = f'{tmp_folder}/{id_carta}_tmp.tif'

            # merge collected
            # here we remove the alpha channel `4`
            merge(tiles, indexes=[1, 2, 3], dst_path=file_tmp)

            with rasterio.open(file_tmp) as dst1:
                out_image, out_transform = mask(dst1, [geom], crop=True, pad=True, filled=False)
                out_meta = dst1.meta

            # crop original
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                'src_crs': crs,
                'dst_crs': crs,
                'multithread': True,
                'photometric': 'YCBCR',
                'compress': "JPEG",
                'jpeg_quality': "80",
                "tfw": 'YES'
            })

            # save original projection
            with rasterio.open(f'{output_folder_layer_crs}/{layer_name}__{id_carta}_{crs.replace(":", "-")}.tif', "w", **out_meta) as dst1:
                dst1.write(out_image)
                dst1.crs = crs

                # build overviews for geoserver
                dst1.build_overviews(
                    [2, 4, 8, 16, 32, 64, 128, 256], Resampling.average)

                dst_crs = calculate_epsg(faja)

                if not dst_crs:
                    print(
                        f'{Fore.RED}Error: {id_carta} has no projection{Style.RESET_ALL}')
                    continue

                transform, width, height = calculate_default_transform(
                    dst1.crs, dst_crs, dst1.width, dst1.height, *dst1.bounds)
                kwargs = dst1.meta.copy()
                kwargs.update({
                    'crs': dst_crs,
                    'transform': transform,
                    'width': width,
                    'height': height,
                    'multithread': True,
                    'compress': "JPEG",
                    'photometric': 'YCBCR',
                    'jpeg_quality': "80",
                    "tfw": 'YES'
                })

                output_folder_layer_crs = f'{output_folder_layer}/{dst_crs.replace(":","-")}'

                if not os.path.exists(output_folder_layer_crs):
                    os.makedirs(output_folder_layer_crs)

                # save reprojected
                with rasterio.open(f'{output_folder_layer_crs}/{layer_name}__{id_carta}_{dst_crs.replace(":","-")}.tif', "w", **kwargs) as dst2:
                    for i in range(1, dst1.count + 1):
                        reproject(
                            source=rasterio.band(dst1, i),
                            destination=rasterio.band(dst2, i),
                            src_transform=dst1.transform,
                            src_crs=dst1.crs,
                            dst_transform=transform,
                            dst_crs=dst_crs,
                            resampling=Resampling.nearest)

        print('\t')
        print('--> PROCESS WAS COMPLETED <--')
        print('------------------------------')
        print(f'-> Tiles matched: {matched_count}')
        print('------------------------------')
       
        if os.path.exists(tmp_folder):
            print(f'-> Removing tmp files...')

    except Exception as error:
        print(f'{Fore.RED}{error}{Style.RESET_ALL}')
        print(traceback.format_exc())


def get_json():
    if os.path.exists(json_tmp):
        with open(json_tmp, 'r') as file:
            return json.load(file)
    else:
        return {
            'count': 0,
            'matched': 0,
            'images': []
        }


def write_json(dict):
    with open(json_tmp, 'w') as outfile:
        json.dump(dict, outfile)


def calculate_epsg(faja):
    if faja == '1':
        dst_crs = 'EPSG:5343'
    elif faja == '2':
        dst_crs = 'EPSG:5344'
    elif faja == '3':
        dst_crs = 'EPSG:5345'
    elif faja == '4':
        dst_crs = 'EPSG:5346'
    elif faja == '5':
        dst_crs = 'EPSG:5347'
    elif faja == '6':
        dst_crs = 'EPSG:5348'
    elif faja == '7':
        dst_crs = 'EPSG:5349'
    else:
        dst_crs = None

    return dst_crs


def get_images():
    types = ('*.png', '*.jpg', '*.jpeg', '*.tiff', '*.tif')
    files_grabbed = []
    for type in types:
        files_grabbed.extend(glob.glob(f'{input_folder}/{type}'))
    return files_grabbed


init()

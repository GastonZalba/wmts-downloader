import os
import glob
import shutil
import tempfile
import rasterio

from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS

from shapely.geometry import box

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

def init():
    try:
        global output_folder, collect_path_images, crs
        
        count = 0

        if not os.path.exists(tmp_folder):
            os.makedirs(tmp_folder)

        images = get_images()

        collect_path_images = {}

        for image in images:
            file_name = os.path.basename(image)
            layer_name = file_name.split('__')[0]
            attributes = file_name.split('_')
            crs = [x for x in attributes if 'EPSG' in x][0].replace(
                '-', ':')

            with rasterio.open(image, crs=crs) as src:
                bounds_image = box(*src.bounds)

                for index, carta in gdf_cards.iterrows():
                    id_carta = carta['caracteristica_de_hoja']
                    faja = carta['numero_faja']
                    geom = carta.geometry

                    if bounds_image.intersects(geom):

                        # check bands
                        number_bands = src.meta['count']

                        if number_bands != 4:

                            band_1 = src.read(1)
                            band_2 = src.read(2)

                            out_meta = src.meta

                            out_meta.update({
                                "count": 4
                            })

                            image = f'{tmp_folder}/{file_name}'

                            with rasterio.open(f'{image}', 'w', **out_meta,) as dst:
                                dst.write(band_1, 1)
                                dst.write(band_1, 2)
                                dst.write(band_1, 3)
                                dst.write(band_2, 4)

                        if not id_carta in collect_path_images:
                            collect_path_images[id_carta] = {
                                "path": image,
                                "faja": faja,
                                "id_carta": id_carta,
                                "geom": geom,
                                "images": []
                            }
                        else:
                            collect_path_images[id_carta]['images'].append(
                                image)

                        print(f'-> Matched image {file_name} with {id_carta}')
                        count += 1

        print('-> Starting conversions')

        for index in collect_path_images:

            images_collected = collect_path_images[index]
            faja = images_collected['faja']
            geom = images_collected['geom']
            images = images_collected['images']
            id_carta = images_collected['id_carta']

            output_folder_layer = f'{output_folder}/{layer_name}'

            output_folder_layer_crs = f'{output_folder_layer}/{crs.replace(":", "-")}'

            if not os.path.exists(output_folder_layer_crs):
                os.makedirs(output_folder_layer_crs)

            file_tmp = f'{tmp_folder}/{id_carta}_tmp.tif'

            # merge collected
            merge(images, indexes=[1, 2, 3, 4], dst_path=file_tmp)

            with rasterio.open(file_tmp) as src:
                out_image, out_transform = mask(src, [geom], crop=True)
                out_meta = src.meta

            # crop
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                'src_crs': crs,
                'dst_crs': crs
            })

            # save original projection
            with rasterio.open(f'{output_folder_layer_crs}/{layer_name}__{id_carta}_{crs.replace(":", "-")}.tif', "w", **out_meta) as src:
                src.write(out_image)
                src.crs = crs

                dst_crs = None

                # save reprojected
                if faja == '4':
                    dst_crs = 'EPSG:5346'
                elif faja == '5':
                    dst_crs = 'EPSG:5347'
                elif faja == '6':
                    dst_crs = 'EPSG:5348'

                if not dst_crs:
                    print(f'{Fore.RED}Error: {id_carta} has no projection {Style.RESET_ALL}')
                    continue

                transform, width, height = calculate_default_transform(
                    src.crs, dst_crs, src.width, src.height, *src.bounds)
                kwargs = src.meta.copy()
                kwargs.update({
                    'crs': dst_crs,
                    'transform': transform,
                    'width': width,
                    'height': height
                })

                output_folder_layer_crs = f'{output_folder_layer}/{dst_crs.replace(":","-")}'

                if not os.path.exists(output_folder_layer_crs):
                    os.makedirs(output_folder_layer_crs)

                # save reprojected
                with rasterio.open(f'{output_folder_layer_crs}/{layer_name}__{id_carta}_{dst_crs.replace(":","-")}.tif', "w", **kwargs) as dst:
                    for i in range(1, src.count + 1):
                        reproject(
                            source=rasterio.band(src, i),
                            destination=rasterio.band(dst, i),
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=transform,
                            dst_crs=dst_crs,
                            resampling=Resampling.nearest)
        
        if os.path.exists(tmp_folder):
            print(f'-> Removing tmp files...')
            shutil.rmtree(tmp_folder)

        print('\t')
        print('--> PROCESS WAS COMPLETED <--')
        print('------------------------------')
        print(f'-> Images matched: {count}')
        print('------------------------------')

    except Exception as error:
        print(f'{Fore.RED}{error}{Style.RESET_ALL}')
        print(traceback.format_exc())


def get_images():
    types = ('*.png', '*.jpg', '*.jpeg', '*.tiff', '*.tif')
    files_grabbed = []
    for type in types:
        files_grabbed.extend(glob.glob(f'{input_folder}/{type}'))
    return files_grabbed


init()

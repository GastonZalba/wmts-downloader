import os
import glob
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge
from shapely.geometry import box

import traceback
import geopandas as gpd
from colorama import init, Fore, Style

# fix colorama colors in windows console
init(convert=True)

input_folder = 'output/cartas_50k/EPSG-3857/14'
output_folder = 'output/merged'
gdf_cards = gpd.read_file('cartas.geojson')

def init():
    try:
        global output_folder, collect_path_images

        images = get_images()

        for index, carta in gdf_cards.iterrows():
            id_carta = carta['caracteristica_de_hoja']
            faja = carta['numero_faja']
            geom = carta.geometry

            print('-> Proccessing', id_carta, faja)

            collect_path_images = []

            for image in images:
                file_name = os.path.basename(image)
                layer_name = file_name.split('__')[0]
                attributes = file_name.split('_')
                crs = [x for x in attributes if 'EPSG' in x][0].replace(
                    '-', ':')

                with rasterio.open(image, crs=crs) as src:
                    bounds_image = box(*src.bounds)

                    if bounds_image.intersects(geom):
                        collect_path_images.append(image)
                        print(f'-> Matched image {file_name} with {id_carta}')
                        print(bounds_image)
                        print(geom)
                    #else:
                        #print(f'-> Unmatched image {file_name} with {id_carta}')

            if len(collect_path_images) < 1:
                print('--> Skip')
                continue

            output_folder_layer = f'{output_folder}/{layer_name}'

            output_folder_layer_crs = f'{output_folder_layer}/{crs.replace(":", "-")}'

            if not os.path.exists(output_folder_layer_crs):
                os.makedirs(output_folder_layer_crs)

            file_tmp = f'{output_folder_layer_crs}/{id_carta}_tmp.tif'

            # merge collected
            merge(collect_path_images, indexes=[1, 2], dst_path=file_tmp)
            
            print(file_tmp, faja)
            print(geom)
            print(collect_path_images)

            with rasterio.open(file_tmp) as src:
                out_image, out_transform = mask(src, [geom], crop=True)
                out_meta = src.meta

            # crop
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })

            with rasterio.open(f'{output_folder_layer_crs}/{id_carta}.tif', "w", **out_meta) as dest:
                dest.write(out_image)

            # save 3857

            # save reprojected
            if faja == 4:
                dst_crs = 'EPSG:5346'
            elif faja == 5:
                dst_crs = 'EPSG:5347'
            elif faja == 6:
                dst_crs = 'EPSG:5348'

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

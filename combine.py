import os
import glob
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge
from shapely.geometry import Polygon
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
        global output_folder

        images = get_images()

        for index, carta in gdf_cards.iterrows():
            id_carta = carta['carac']
            faja = carta['num_faja']
            geom = carta['geometry']

            print('-> Proccessing', id_carta, faja)
            
            collect_path_images = []

            for image in images:
                file_name = os.path.basename(image)
                layer_name = file_name.split('__')[0]
                attributes = file_name.split('_')
                crs = [x for x in attributes if 'EPSG' in x][0].replace('-', ':')

                with rasterio.open(image, crs=crs) as src:
                    bounds = src.bounds
                    bounds = bbox(bounds.left, bounds.bottom, bounds.right, bounds.top)
                    gdf_image = gpd.GeoDataFrame(index=[0], crs=crs, geometry=[bounds]).iloc[0]
                   
                    if geom.intersects(gdf_image['geometry']):
                        collect_path_images.append(image)
                        print(f'-> Matched image {file_name} with {id_carta}')
                    else:
                        print(f'-> Unmatched image {file_name} with {id_carta}')
            
            if len(collect_path_images) < 1:
                continue

            output_folder_layer = f'{output_folder}/{layer_name}'

            output_folder_layer_crs = f'{output_folder_layer}/{crs.replace(":", "-")}'

            if not os.path.exists(output_folder_layer_crs):
                os.makedirs(output_folder_layer_crs)

            # merge collected
            mosaic = merge(collect_path_images, indexes=[1,2], dst_path=f'{output_folder_layer_crs}/{id_carta}.tif')

            print(f'-> Merged tiles {mosaic}')

            # crop 
            # out_image, out_transform = mask(merged, geom, crop=True)

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

# function to return polygon
def bbox(long0, lat0, lat1, long1):
    return Polygon([[long0, lat0],
                    [long1,lat0],
                    [long1,lat1],
                    [long0, lat1]])

def get_images():
    types = ('*.png', '*.jpg', '*.jpeg', '*.tiff', '*.tif')
    files_grabbed = []
    for type in types:
        files_grabbed.extend(glob.glob(f'{input_folder}/{type}'))
    return files_grabbed

init()
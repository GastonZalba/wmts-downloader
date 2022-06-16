import os
import requests
from requests.models import PreparedRequest
from params import *
import xmltodict
import traceback
from colorama import init, Fore, Style
from owslib.wmts import WebMapTileService
import shutil

# fix colorama colors in windows console
init(convert=True)

try:

    # check if output folder exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for d in dw:

        url = d['url']

        version = d['version'] if 'version' in d.keys() else '1.3.0'

        params = {
            'version': version,
            'service': 'WMS',
            'request': 'GetCapabilities'
        }

        req = PreparedRequest()
        req.prepare_url(url, params)

        resp = requests.get(req.url)

        xml = xmltodict.parse(resp.content)

        layers = xml['Capabilities']['Contents']['Layer']

        format = d['format']

        zoom = d['zoom']

        proj =  d['epsg']

        layer_id = d['layer']

        for layer in layers:
            if layer['ows:Identifier'] == d['layer']:
                title = layer["ows:Title"]
                abstract = layer["ows:Abstract"]
                formats = layer["Format"]
                tile_matrixs = layer['TileMatrixSetLink']
                for tm in tile_matrixs:

                    tile_matrix_set = tm['TileMatrixSet']

                    if tile_matrix_set == proj:

                        tile_matrix_limits = tm['TileMatrixSetLimits']['TileMatrixLimits']

                        for tml in tile_matrix_limits:

                            z = int(tml['TileMatrix'].split(":")[-1])

                            if z == zoom:
                                limit = tml
                        
                        # check if output folder exists
                        layer_folder = f'{output_folder}\\{layer_id}'

                        if os.path.exists(layer_folder):
                            shutil.rmtree(layer_folder)
                        
                        os.makedirs(layer_folder)

                        wmts = WebMapTileService(url)
                        
                        tile_matrix = limit['TileMatrix']
                        row = limit['MinTileRow']
                        col = limit['MinTileCol']

                        img = wmts.gettile(
                            url,
                            layer=layer_id,
                            tilematrixset=tile_matrix_set,
                            tilematrix=tile_matrix,
                            row=row,
                            column=col,
                            format=format
                        )                        

                        out = open(f'{layer_folder}\\{layer_id}_zoom-{zoom}_col-{col}_row-{row}.png', 'wb')
                        bytes_written = out.write(img.read())
                        out.close()

except Exception as error:
    print(f'{Fore.RED}{error}{Style.RESET_ALL}')
    print(traceback.format_exc())

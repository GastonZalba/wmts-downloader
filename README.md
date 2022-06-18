# wmts-downloader
Script to download raster layers from WMTS services. The proccess downloads each geoserver tile (256x256), geolocates it, and creates a [world file](https://en.wikipedia.org/wiki/World_file) for each tile. These can then be merged, cropped (and maybe reprojected) using gdal, qgis, etc. Keep it in mind that if the target zoom level is to high, and/or the area of interest is big enough, each execution can trigger thousands or millions of requests to the server, so use this with caution. To avoid overloading the server and facilitate the process, the script can resume incompleted jobs and add some sleep time betweeen requests. Running it multiples times with the same parameters, it will continue from the last downloaded tile.

## Installation
- Create local enviroment running `python -m venv .venv` (install [virtualenv](https://virtualenv.pypa.io/en/latest/ if you don't have it)
- Load local enviroment: `.venv\Scripts\activate`
- Install using `pip install -r requirements.txt`

## Instructions
- Load local enviroment `.venv\Scripts\activate`
- Run `python wmts-downloader.py --help` to show all available options and arguments
- Run the script with something like this `python wmts-downloader.py https://imagenes.ign.gob.ar/geoserver/cartas_mosaicos/gwc/service/wmts --layer cartas_50k --zoom 14 --limit 1000 --bbox -7092196.7637569485232234 -5039771.7783368593081832 -6263492.7329376600682735 -3889283.7355505060404539`
- You can use the `limit` and `sleep` arguments to avoid overloading the target server. You can later rerun the script to continue from the last downloaded tile.
- Check the console for details and the `/output` folder (the default) for the tiles

## Limitatios
- The projection EPSG:3857 is currently the only one supported

## Todo
- Add EPSG:4326 support
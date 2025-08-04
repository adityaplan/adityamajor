import ee
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Google Earth Engine
try:
    ee.Initialize()
    logger.info("GEE initialized successfully")
except Exception as e:
    logger.error(f"GEE initialization failed: {str(e)}")
    ee.Authenticate()
    ee.Initialize()

def calculate_ndvi(image):
    try:
        ndvi = image.normalizedDifference(['B5', 'B4']).rename('NDVI')
        return image.addBands(ndvi)
    except Exception as e:
        logger.error(f"NDVI calculation error: {str(e)}")
        raise

def calculate_evi(image):
    try:
        evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
            {'NIR': image.select('B5'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}
        ).rename('EVI')
        return image.addBands(evi)
    except Exception as e:
        logger.error(f"EVI calculation error: {str(e)}")
        raise

def calculate_ndwi(image):
    try:
        ndwi = image.normalizedDifference(['B3', 'B5']).rename('NDWI')
        return image.addBands(ndwi)
    except Exception as e:
        logger.error(f"NDWI calculation error: {str(e)}")
        raise

def calculate_ndbi(image):
    try:
        ndbi = image.normalizedDifference(['B6', 'B5']).rename('NDBI')
        return image.addBands(ndbi)
    except Exception as e:
        logger.error(f"NDBI calculation error: {str(e)}")
        raise

def get_landsat_data(roi, start_date, end_date):
    try:
        landsat = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
            .filterBounds(roi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUD_COVER', 20))
        
        count = landsat.size().getInfo()
        if count == 0:
            raise Exception("No Landsat images found for the given region and time")
        
        landsat = landsat.median()
        landsat = landsat.select(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'ST_B10'])
        
        scale_factor = 0.0000275
        offset = -0.2
        sr_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6']
        scaled_sr = landsat.select(sr_bands).multiply(scale_factor).add(offset)
        
        thermal_scaled = landsat.select('ST_B10').multiply(0.00341802).add(149.0)
        
        landsat = scaled_sr.addBands(thermal_scaled).rename(['B2', 'B3', 'B4', 'B5', 'B6', 'LST'])
        
        landsat = calculate_ndvi(landsat)
        landsat = calculate_evi(landsat)
        landsat = calculate_ndwi(landsat)
        landsat = calculate_ndbi(landsat)
        logger.info("Landsat data processed successfully")
        return landsat
    except Exception as e:
        logger.error(f"Landsat error: {str(e)}")
        raise

def get_modis_albedo(roi, start_date, end_date):
    try:
        modis = ee.ImageCollection('MODIS/006/MCD43A3') \
            .filterBounds(roi) \
            .filterDate(start_date, end_date) \
            .select('Albedo_BSA_Band1')
        
        count = modis.size().getInfo()
        if count == 0:
            raise Exception("No MODIS albedo images found")
        
        modis = modis.median()
        logger.info("MODIS albedo processed successfully")
        return modis
    except Exception as e:
        logger.error(f"MODIS error: {str(e)}")
        raise

def get_sentinel5p_air_quality(roi, start_date, end_date, pollutant='NO2'):
    try:
        dataset = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_' + pollutant) \
            .filterBounds(roi) \
            .filterDate(start_date, end_date) \
            .select('tropospheric_NO2_column_number_density')
        
        count = dataset.size().getInfo()
        if count == 0:
            raise Exception(f"No Sentinel-5P {pollutant} images found")
        
        dataset = dataset.median()
        logger.info(f"Sentinel-5P {pollutant} processed successfully")
        return dataset
    except Exception as e:
        logger.error(f"Sentinel-5P error: {str(e)}")
        raise

def get_srtm_dem(roi):
    try:
        dem = ee.Terrain.products(ee.Image('USGS/SRTMGL1_003')).select(['elevation', 'slope', 'aspect'])
        logger.info("SRTM DEM processed successfully")
        return dem
    except Exception as e:
        logger.error(f"SRTM error: {str(e)}")
        raise

def get_surface_water(roi):
    try:
        water = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence')
        logger.info("Surface water processed successfully")
        return water
    except Exception as e:
        logger.error(f"Surface water error: {str(e)}")
        raise

def process_satellite_data(center, radius_km):
    try:
        roi = ee.Geometry.Point(center[1], center[0]).buffer(radius_km * 1000)
        start_date = '2023-01-01'
        end_date = '2023-12-31'
        
        landsat = get_landsat_data(roi, start_date, end_date)
        albedo = get_modis_albedo(roi, start_date, end_date)
        dem = get_srtm_dem(roi)
        water = get_surface_water(roi)
        no2 = get_sentinel5p_air_quality(roi, start_date, end_date, 'NO2')
        
        map_data = {}
        for band in ['NDVI', 'EVI', 'NDWI', 'NDBI', 'LST']:
            map_id = landsat.select(band).getMapId({
                'min': -0.2 if band != 'LST' else 290,
                'max': 0.8 if band != 'LST' else 310,
                'palette': ['blue', 'yellow', 'green'] if band in ['NDVI', 'EVI'] else ['red', 'yellow', 'blue']
            })
            if 'tile_fetcher' not in map_id:
                logger.error(f"Failed to get map ID for {band}")
                raise Exception(f"Failed to get map ID for {band}")
            map_data[band] = map_id['tile_fetcher'].url_format
        map_id = albedo.getMapId({'min': 0, 'max': 0.3, 'palette': ['black', 'white']})
        map_data['albedo'] = map_id['tile_fetcher'].url_format if 'tile_fetcher' in map_id else ''
        map_id = dem.select('elevation').getMapId({'min': 0, 'max': 1000, 'palette': ['green', 'brown']})
        map_data['elevation'] = map_id['tile_fetcher'].url_format if 'tile_fetcher' in map_id else ''
        map_id = water.getMapId({'min': 0, 'max': 100, 'palette': ['white', 'blue']})
        map_data['water'] = map_id['tile_fetcher'].url_format if 'tile_fetcher' in map_id else ''
        map_id = no2.getMapId({'min': 0, 'max': 0.0001, 'palette': ['green', 'yellow', 'red']})
        map_data['no2'] = map_id['tile_fetcher'].url_format if 'tile_fetcher' in map_id else ''
        
        logger.info("Map data generated successfully")
        return map_data
    except Exception as e:
        logger.error(f"Process satellite data error: {str(e)}")
        raise
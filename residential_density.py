'''----------------------------------------------------------------------------------
 Name: Residential Density Calculator
 Source: residential_density.py
 Version: ArcGIS 10.5 or later
 Authors: Ehsan Najafi
----------------------------------------------------------------------------------'''
###  Sample data for test: /data_test/sample_data.gdb


### Input data
in_sample_points = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\sample_participants_home"
in_landuse_polygon = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\sample_landuse"
in_network_dataset = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\pedstrain_network_ND"

buffer_in_meters = 1000

dict_landuse_codes = {
	"Residental": "1", 
	"Park and green spaces": "2", 
	"Urban services": "3",
	"Industrial": "4", 
	"Commercial": "5", 
	"Orchards and Agricultural": "6", 
	"Barren land": "7",
}

### Import python modules
import arcpy, os, sys, tempfile
import math

### Cacluate Radius Buffer Area
area_buffer_in_m2 = math.pi * (buffer_in_meters ** 2)

### Set environment settings
reload(sys)
sys.setdefaultencoding('utf8')
reload(sys)
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = True

### Set local address to save temp data in user temp
env_path = tempfile.gettempdir() + "\\" + "PY_" + time.strftime("%Y%m%d_%I%M%S%p")
if not os.path.exists(env_path):
	os.makedirs(env_path)

### Create Temporary Geodatabase
gdb_temp_path = os.path.join(env_path, "temp.gdb")
arcpy.CreateFileGDB_management(os.path.dirname(gdb_temp_path), os.path.basename(gdb_temp_path))

### Create copy featureclass for sample points
in_sample_points_temp = os.path.join(gdb_temp_path, "in_sample_points_temp") 
if arcpy.Exists(in_sample_points_temp):
	arcpy.Delete_management(in_sample_points_temp)
arcpy.FeatureClassToFeatureClass_conversion(in_sample_points, os.path.dirname(in_sample_points_temp), os.path.basename(in_sample_points_temp), "")
in_sample_layer = arcpy.MakeFeatureLayer_management(in_sample_points_temp, "in_sample_layer", "", "")


### Create featureclass for SELECT residential landuse from all landuse featureclass
out_residential_landuse_fc = os.path.join(gdb_temp_path, "out_residential_landuse_fc") 
if arcpy.Exists(out_residential_landuse_fc):
	arcpy.Delete_management(out_residential_landuse_fc)
arcpy.FeatureClassToFeatureClass_conversion(in_landuse_polygon, os.path.dirname(out_residential_landuse_fc), os.path.basename(out_residential_landuse_fc), "LANDUSE_CODE = " + dict_landuse_codes["Residental"])


### Calculate Network Buffer through service area analysis for each sample ponts

## Create a new service-area layer. 
outServiceAreaLayer = arcpy.na.MakeServiceAreaLayer(in_network_dataset, "outNALayer", "Length", "TRAVEL_FROM", str(buffer_in_meters), "DETAILED_POLYS", "NO_MERGE", "RINGS", "")

## Get the layer object from the result object. The service-area layer
outNALayer = outServiceAreaLayer.getOutput(0)
subLayerNames = arcpy.na.GetNAClassNames(outNALayer)
facilitiesLayerName = subLayerNames["Facilities"]

## Load the candidate store locations as facilities using default search tolerance and field mappings.
facilityFieldMappings = arcpy.na.NAClassFieldMappings(outNALayer, facilitiesLayerName)
arcpy.na.AddLocations(outNALayer, facilitiesLayerName, in_sample_layer, facilityFieldMappings, "", exclude_restricted_elements = "EXCLUDE")

## Solve the service-area layer
arcpy.Solve_na(outNALayer, "SKIP", "TERMINATE", "")

## Make polygon feature
out_service_area = os.path.join(gdb_temp_path, "out_service_area") 
if arcpy.Exists(out_service_area):
	arcpy.Delete_management(out_service_area)
arcpy.CopyFeatures_management("outNALayer/Polygons", out_service_area, "", "0", "0", "0")

## Make ID dictionary
dict_ID_Area = {}
with arcpy.da.SearchCursor(in_sample_layer, ["OBJECTID", "ID"]) as cursor:
	for row in cursor:
		oid = row[0]
		dict_ID_Area[oid] = row[1]

## Make network area dictionary
dict_area_network = {}
arcpy.AddField_management(out_service_area, "SAMPLE_ID", "LONG")
with arcpy.da.UpdateCursor(out_service_area ,["FacilityID", "SAMPLE_ID", "Shape_Area"]) as UC:
	for row in UC:
		row[1] = dict_ID_Area[row[0]]
		dict_area_network[row[1]] = row[2]
		UC.updateRow(row)

### Make Area Field for Service Area Feature Class
sr = arcpy.Describe(out_service_area).spatialReference
arcpy.AddGeometryAttributes_management(out_service_area, "AREA", "", "SQUARE_KILOMETERS", sr)

### Create Feature Layer for Service Area Feature Class
in_service_area_lyr = arcpy.MakeFeatureLayer_management(out_service_area, "service_area_lyr", "", "")


### Create New Field 'Residential_Density' in Sample Points Feature Class
Residential_Density_field = "Residential_Density_network_" + str(buffer_in_meters) + "m"
if str(arcpy.ListFields(in_sample_points, Residential_Density_field)) == "[]":
	arcpy.AddField_management(in_sample_points, Residential_Density_field, "DOUBLE")

### Find Intersect Count of Residential Polygons inside Network buffers
dict_intersect_count = {}
dict_network_buffer_area = {}
out_service_area_intersect = gdb_temp_path + "\\" + "out_service_area_intersect"
if arcpy.Exists(out_service_area_intersect):
	arcpy.Delete_management(out_service_area_intersect)
arcpy.SpatialJoin_analysis(out_service_area, out_residential_landuse_fc, out_service_area_intersect, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "INTERSECT", "", "")

with arcpy.da.SearchCursor(out_service_area_intersect, ["SAMPLE_ID", "JOIN_COUNT", "POLY_AREA"]) as cursor:
	for row in cursor:
		dict_intersect_count[row[0]] = row[1]
		dict_network_buffer_area[row[0]] = row[2]

### Update Field 'Residential_Density' in Sample Points Feature Class
with arcpy.da.UpdateCursor(in_sample_points, ["ID", Residential_Density_field]) as UC:
	for row in UC:
		sample_id = row[0]
		intersect_count = dict_intersect_count[sample_id]
		network_buffer_area = dict_network_buffer_area[sample_id]
		row[1] = float(intersect_count / network_buffer_area)
		UC.updateRow(row)






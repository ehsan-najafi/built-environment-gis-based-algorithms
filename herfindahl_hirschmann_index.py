'''----------------------------------------------------------------------------------
 Name: Herfindahl-Hirschmann Index
 Source: herfindahl_hirschmann_index.py
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
	"1": "Residental", 
	"2": "Park and green spaces", 
	"3": "Urban services",
	"4": "Industrial", 
	"5": "Commercial", 
	"6": "Orchards and Agricultural", 
	"7": "Barren land",
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

### Create Feature Layer for Service Area Feature Class
in_service_area_lyr = arcpy.MakeFeatureLayer_management(out_service_area, "service_area_lyr", "", "")

### Create copy featureclass for Landuse Polygon
in_landuse_polygon_temp = os.path.join(env_path, "in_landuse_polygon_temp.shp") 
if arcpy.Exists(in_landuse_polygon_temp):
	arcpy.Delete_management(in_landuse_polygon_temp)
arcpy.FeatureClassToFeatureClass_conversion(in_landuse_polygon, os.path.dirname(in_landuse_polygon_temp), os.path.basename(in_landuse_polygon_temp), "")


### Create New Field 'Herfindahl_Hirschmann_Index' in Sample Points Feature Class
Herfindahl_Hirschmann_Index_field = "Herfindahl_Hirschmann_Index_" + str(buffer_in_meters) + "m"
if str(arcpy.ListFields(in_sample_points, Herfindahl_Hirschmann_Index_field)) == "[]":
	arcpy.AddField_management(in_sample_points, Herfindahl_Hirschmann_Index_field, "DOUBLE")

### Make List of Sample Points
list_ids = []
with arcpy.da.SearchCursor(in_sample_points, ["ID"], "") as cursor:
	for row in cursor:
		list_ids.append(int(row[0]))


### Cacluate 'Herfindahl_Hirschmann_Index' and 'Residential_LU_Percent'
dict_sum_length = {}
for selected_id in list_ids:
	arcpy.management.SelectLayerByAttribute(in_service_area_lyr, "NEW_SELECTION", "SAMPLE_ID = " + str(selected_id))
	if arcpy.Describe(in_service_area_lyr).FIDSet != '':
		### Clip Landuse Features inside sample point network buffer
		out_clip_landuse = gdb_temp_path + "\\" + "clip_road_" + str(selected_id)
		arcpy.Clip_analysis(in_landuse_polygon_temp, in_service_area_lyr, out_clip_landuse, "")
		
		### Cacluate Sum of Area of Each Landuse class
		out_summrize_table = gdb_temp_path + "\\" + "out_summrize_" + str(selected_id)		
		arcpy.Statistics_analysis(out_clip_landuse, out_summrize_table, [["Shape_Area", "SUM"]], case_field='LANDUSE_CO')
		
		### Cacluate Both Indexes
		Herfindahl_Hirschmann_Index = 0
		sum_area_all_landuse = 0
		with arcpy.da.SearchCursor(out_summrize_table, ["SUM_Shape_Area"]) as cursor:
			for row in cursor:
				sum_area_all_landuse += row[0]
		with arcpy.da.SearchCursor(out_summrize_table, ["LANDUSE_CO", "SUM_Shape_Area"]) as cursor:
			for row in cursor:
				lu_code = row[0]
				lu_area = row[1]
				lu_area_percentage = (lu_area / sum_area_all_landuse)
				Herfindahl_Hirschmann_Index += (lu_area_percentage ** 2)


		### Update Field 'Herfindahl_Hirschmann_Index' in Sample Points Feature Class
		with arcpy.da.UpdateCursor(in_sample_points, [Herfindahl_Hirschmann_Index_field], "ID = " + str(selected_id)) as UC:
			for row in UC:
				row[0] = Herfindahl_Hirschmann_Index
				UC.updateRow(row)

		### Remove Temporary Layers
		arcpy.Delete_management(out_clip_landuse)	
		arcpy.Delete_management(out_summrize_table)	






'''----------------------------------------------------------------------------------
 Name: Effective Walkable Area
 Source: effective_walkable_area.py
 Version: ArcGIS 10.5 or later
 Authors: Ehsan Najafi
----------------------------------------------------------------------------------'''
###  Sample data for test: /data_test/sample_data.gdb


### Input data
in_sample_points = r"D:\built-environment-gis-based-algorithms\data_test\sample_data.gdb\sample_participants_home"
in_network_dataset = r"D:\built-environment-gis-based-algorithms\data_test\sample_data.gdb\pedstrain_network_ND"

buffer_in_meters = 1000

### Import python modules
import arcpy, os, sys, tempfile

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


### Create Radius Coverage Buffer Feature Class
in_sample_buffer_fc = gdb_temp_path + "\\" + "in_sample_buffer_fc"
if arcpy.Exists(in_sample_buffer_fc):
	arcpy.Delete_management(in_sample_buffer_fc)
arcpy.Buffer_analysis(in_sample_points, in_sample_buffer_fc, str(buffer_in_meters) + " Meters", "FULL", "ROUND", "", "", "PLANAR")
in_sample_buffer_lyr = arcpy.MakeFeatureLayer_management(in_sample_buffer_fc, "in_sample_buffer_lyr", "", "")
dict_area_buffer = {}
with arcpy.da.SearchCursor(in_sample_buffer_fc, ["ID", "Shape_Area"]) as cursor:
	for row in cursor:
		oid = row[0]
		dict_area_buffer[oid] = row[1]


### Create New Field in Sample Points Feature Class
sum_routes_field_name = "EFFECTIVE_ACC_ROUTE_" + str(buffer_in_meters) + "m"
if str(arcpy.ListFields(in_sample_points, sum_routes_field_name)) == "[]":
	arcpy.AddField_management(in_sample_points, sum_routes_field_name, "DOUBLE")

### Update Field in Sample Points Feature Class
with arcpy.da.UpdateCursor(in_sample_points, ["ID", sum_routes_field_name]) as UC:
	for row in UC:
		try:
			sample_id = row[0]
			sum_area_buffer = dict_area_buffer[sample_id]
			sum_area_network = dict_area_network[sample_id]
			row[1] = float(sum_area_network / sum_area_buffer)
			UC.updateRow(row)
		except:
			pass




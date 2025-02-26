'''----------------------------------------------------------------------------------
 Name: Distance to nearest Park and Sport facility
 Source: accessibility_distance_to_nearest_park_and_sport_facility.py
 Version: ArcGIS 10.5 or later
 Authors: Ehsan Najafi
----------------------------------------------------------------------------------'''
###  Sample data for test: /data_test/sample_data.gdb

### Input data
in_origins_points = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\sample_participants_home"
in_network_dataset = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\pedstrain_network_ND"

in_poi_points = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\park"
poi_name = "park"

# in_poi_points = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\sport"
# poi_name = "sport"


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
in_origins_points_temp = os.path.join(gdb_temp_path, "in_origins_points_temp") 
if arcpy.Exists(in_origins_points_temp):
	arcpy.Delete_management(in_origins_points_temp)
arcpy.FeatureClassToFeatureClass_conversion(in_origins_points, os.path.dirname(in_origins_points_temp), os.path.basename(in_origins_points_temp), "")

### Create Feature Layer for sample points
origin_layer = arcpy.MakeFeatureLayer_management(in_origins_points_temp, "origin_layer", "", "")

### Create copy featureclass for POI points
in_poi_points_temp = os.path.join(gdb_temp_path, "in_poi_points_temp") 
if arcpy.Exists(in_poi_points_temp):
	arcpy.Delete_management(in_poi_points_temp)
arcpy.FeatureClassToFeatureClass_conversion(in_poi_points, os.path.dirname(in_poi_points_temp), os.path.basename(in_poi_points_temp), "")

### Create Feature Layer for POI points
poi_layer = arcpy.MakeFeatureLayer_management(in_poi_points_temp, "poi_layer", "", "")


### Create Origins(Samples) Dictionary
dict_origins_ID = {}
with arcpy.da.SearchCursor(in_origins_points_temp, ["OBJECTID", "ID"]) as cursor:
	for row in cursor:
		oid = row[0]
		dict_origins_ID[oid] = row[1]

### Create Destinations(POIs) Dictionary
dict_poi_ID_Area = {}
with arcpy.da.SearchCursor(in_poi_points_temp, ["OBJECTID", "POI_ID", "poi_area"]) as cursor:
	for row in cursor:
		oid = row[0]
		dict_poi_ID_Area[oid] = [row[1], row[2]]


################ CALCULATE DISTANCE TO NEAREST FACILITY ##############

### Set local variables
# output_path_shape = "NO_LINES"
output_path_shape = "TRUE_LINES_WITH_MEASURES"


### Create a new closest-facility layer. 
closest_count = "1"
outClosestFacilitiyLayer = arcpy.na.MakeClosestFacilityLayer(in_network_dataset, "outNALayer", "Length", "TRAVEL_TO", "", closest_count, "", "ALLOW_UTURNS", "", "NO_HIERARCHY", "", output_path_shape, "", "")

### Get the layer object from the result object. The closest-facility layer
outNALayer = outClosestFacilitiyLayer.getOutput(0)
subLayerNames = arcpy.na.GetNAClassNames(outNALayer)
facilitiesLayerName = subLayerNames["Facilities"]
incidentsPointsLayerName = subLayerNames["Incidents"]

### Add POIs as facility locations to network analysis
facilityFieldMappings = arcpy.na.NAClassFieldMappings(outNALayer, facilitiesLayerName)
arcpy.na.AddLocations(outNALayer, facilitiesLayerName, poi_layer, facilityFieldMappings, "", exclude_restricted_elements = "EXCLUDE")

### Add samples as demand locations to network analysis
demandFieldMappings = arcpy.na.NAClassFieldMappings(outNALayer, incidentsPointsLayerName)
arcpy.na.AddLocations(outNALayer,incidentsPointsLayerName ,origin_layer, demandFieldMappings, "", exclude_restricted_elements = "EXCLUDE")

### Solve network analysis
arcpy.Solve_na(outNALayer, "SKIP", "TERMINATE", "")

### Make Route Lines as Featureclass
in_closest_route = os.path.join(gdb_temp_path, "in_closest_route") 
if arcpy.Exists(in_closest_route):
	arcpy.Delete_management(in_closest_route)
arcpy.CopyFeatures_management("outNALayer/Routes", in_closest_route, "", "0", "0", "0")

### Add field
arcpy.AddField_management(in_closest_route, "ORG_ID", "LONG")
arcpy.AddField_management(in_closest_route, "POI_ID", "LONG")
with arcpy.da.UpdateCursor(in_closest_route ,["IncidentID", "FacilityID", "ORG_ID", "POI_ID"]) as UC:
	for row in UC:
		row[2] = dict_origins_ID[row[0]]
		poi_ID_Area = dict_poi_ID_Area[row[1]]
		row[3] = poi_ID_Area[0]
		UC.updateRow(row)

### Calculate nearest-distance values
dict_origins_closest_route_dist = {}
with arcpy.da.SearchCursor(in_origins_points, ["ID"]) as cursor:
	for row in cursor:
		org_id = row[0]
		dict_origins_closest_route_dist[org_id] = 0.0
with arcpy.da.SearchCursor(in_closest_route, ["ORG_ID", "POI_ID", "Total_Length"]) as cursor:
	for row in cursor:
		org_id = row[0]
		poi_id = row[1]
		total_length = row[2]
		dict_origins_closest_route_dist[org_id] = total_length


### Create field for calculate nearest-distance value to closest facility (current POI)
poi_near_route = "AM_" + poi_name + "_NEAR_DIST_ROUTE"
if str(arcpy.ListFields(in_origins_points, poi_near_route)) == "[]":
	arcpy.AddField_management(in_origins_points, poi_near_route, "DOUBLE")

### Calculate nearest-distance value to closest facility (current POI)
list_update_fields = ["ID", poi_near_route]
with arcpy.da.UpdateCursor(in_origins_points, list_update_fields) as UC:
	for row in UC:
		origid = row[0]
		try:
			closest_route_dist = float(dict_origins_closest_route_dist[origid])
			row[1] = closest_route_dist
			UC.updateRow(row)
		except:
			pass




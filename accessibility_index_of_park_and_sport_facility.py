'''----------------------------------------------------------------------------------
 Name: Spatial Access to Park and Sport facility
 Source: accessibility_index_of_park_and_sport_facility.py
 Version: ArcGIS 10.5 or later
 Authors: Ehsan Najafi
----------------------------------------------------------------------------------'''
###  Sample data for test: /data_test/sample_data.gdb

### Input data
in_origins_points = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\sample_participants_home"
in_network_dataset = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\pedstrain_network_ND"

# in_poi_points = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\park"
# poi_name = "park"

in_poi_points = r"D:\gis-based-built-environment-algorithms\data_test\sample_data.gdb\sport"
poi_name = "sport"

minimum_parks_area = 0
maximum_parks_area = 10000
minimum_distance_or_time = 0
maximum_distance_or_time = 2000


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


################ CALCULATE GRAVITY-BASED ACCESSIBILITY INDEX ##############

### create OD Cost Matrix Layer
OD_Cost_Matrix = poi_name + "_odcm_layer"
arcpy.MakeODCostMatrixLayer_na(in_network_dataset, OD_Cost_Matrix, "Length", str(maximum_distance_or_time), "" , "", "ALLOW_UTURNS", "", "NO_HIERARCHY", "", "STRAIGHT_LINES", "")

### Add samples as origins locations to network analysis
arcpy.AddLocations_na(OD_Cost_Matrix, "Origins", origin_layer, "", "5000 Meters", "", "roads_drive SHAPE;network_dataset_ND_Junctions NONE", "MATCH_TO_CLOSEST", "APPEND", "NO_SNAP", "5 Meters", "INCLUDE", "roads_drive #;network_dataset_ND_Junctions #")

### Add current POI features as destinations to network analysis
arcpy.AddLocations_na(OD_Cost_Matrix, "Destinations", poi_layer, "Name Name #", "5000 Meters", "", "roads_drive SHAPE;network_dataset_ND_Junctions NONE", "MATCH_TO_CLOSEST", "APPEND", "NO_SNAP", "5 Meters", "INCLUDE", "roads_drive #;network_dataset_ND_Junctions #")

### Solve network analysis
arcpy.Solve_na(OD_Cost_Matrix, "SKIP", "TERMINATE", "")

### Make Route Featureclass
in_route_lines = os.path.join(gdb_temp_path, "in_route_lines") 
if arcpy.Exists(in_route_lines):
	arcpy.Delete_management(in_route_lines)
arcpy.CopyFeatures_management(OD_Cost_Matrix + "/Lines", in_route_lines, "", "0", "0", "0")

### Add field
arcpy.AddField_management(in_route_lines, "ORG_ID", "LONG")
arcpy.AddField_management(in_route_lines, "POI_ID", "LONG")
arcpy.AddField_management(in_route_lines, "POI_AREA", "DOUBLE")

with arcpy.da.UpdateCursor(in_route_lines ,["OriginID", "DestinationID", "ORG_ID", "POI_ID", "POI_AREA"]) as UC:
	for row in UC:
		row[2] = dict_origins_ID[row[0]]
		poi_ID_Area = dict_poi_ID_Area[row[1]]
		row[3] = poi_ID_Area[0]
		row[4] = poi_ID_Area[1]
		UC.updateRow(row)

dict_origins_score_dist_area = {}
with arcpy.da.SearchCursor(in_origins_points, ["ID"]) as cursor:
	for row in cursor:
		org_id = row[0]
		dict_origins_score_dist_area[org_id] = 0.0

with arcpy.da.SearchCursor(in_route_lines, ["ORG_ID", "POI_ID", "POI_AREA", "Total_Length"]) as cursor:
	for row in cursor:
		org_id = row[0]
		poi_id = row[1]
		poi_area = row[2]
		total_length = row[3]
        
        ### Find normalized distance (for current route)
		if total_length <= minimum_distance_or_time:
			score_dist = 1.0
		elif total_length > minimum_distance_or_time and total_length <= maximum_distance_or_time:
			score_dist = (1.0 - (float(total_length - minimum_distance_or_time)/float(maximum_distance_or_time - minimum_distance_or_time)))
		elif total_length > minimum_distance_or_time:
			score_dist = 0.0

        ### Find normalized area (for current route)
		if poi_area >= maximum_parks_area:
			score_area = 1.0
		elif poi_area >= minimum_parks_area and poi_area < maximum_parks_area:
			score_area = float(poi_area - minimum_parks_area)/float(maximum_parks_area-minimum_parks_area)
		elif poi_area < minimum_parks_area:
			score_area = 0.0

        ### Calculate accessibility score            
		score_dist_area = score_area * score_dist
		
        ### Add accessibility scores to dictionary
		if org_id not in dict_origins_score_dist_area.keys():
			dict_origins_score_dist_area[org_id] = score_dist_area
		else:
			dict_origins_score_dist_area[org_id] = dict_origins_score_dist_area[org_id] + score_dist_area


### Create field for calculate accessibility values of current POI
poi_score_dist_area = "AM_" + poi_name + str(maximum_distance_or_time)
if str(arcpy.ListFields(in_origins_points, poi_score_dist_area)) == "[]":
	arcpy.AddField_management(in_origins_points, poi_score_dist_area, "DOUBLE")

### Calculate accessibility values of current POI
list_update_fields = ["ID", poi_score_dist_area]
with arcpy.da.UpdateCursor(in_origins_points, list_update_fields) as UC:
	for row in UC:
		origid = row[0]
		try:
			score_dist_area = float(dict_origins_score_dist_area[origid])
		except:
			score_dist_area = 0.0
		row[1] = score_dist_area
		UC.updateRow(row)



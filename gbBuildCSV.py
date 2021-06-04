import os
import re 
import json
import pandas as pd
import geopandas
from datetime import datetime
import urllib.request
import io

#Initialize workspace
ws = {}
try:
    ws['working'] = os.environ['GITHUB_WORKSPACE']
    ws['logPath'] = os.path.expanduser("~") + "/tmp/log.txt"
except:
    ws['working'] = "/home/dan/git/gbRelease"
    ws['logPath'] = os.path.expanduser("~") + "/tmp/log.txt"

#Load in the ISO lookup table
isoDetails = pd.read_csv(ws['working'] + "/geoBoundaryBot/dta/iso_3166_1_alpha_3.csv",
                        encoding='utf-8')


#Remove any old CSVs for each case
gbOpenCSV = ws["working"] + "/releaseData/geoBoundariesOpen-meta.csv"
gbHumCSV = ws["working"] + "/releaseData/geoBoundariesHumanitarian-meta.csv"
gbAuthCSV = ws["working"] + "/releaseData/geoBoundariesAuthoritative-meta.csv"

try:
    os.remove(gbOpenCSV)
except:
    pass

try:
    os.remove(gbHumCSV)
except:
    pass

try:
    os.remove(gbAuthCSV)
except:
    pass

#Create headers for each CSV
def headerWriter(f):
    f.write("boundaryID,boundaryName,boundaryISO,boundaryYearRepresented,boundaryType,boundaryCanonical,boundarySource-1,boundarySource-2,boundaryLicense,licenseDetail,licenseSource,boundarySourceURL,sourceDataUpdateDate,buildUpdateDate,Continent,UNSDG-region,UNSDG-subregion,worldBankIncomeGroup,apiURL,admUnitCount,meanVertices,minVertices,maxVertices,meanPerimeterLengthKM,minPerimeterLengthKM,maxPerimeterLengthKM,meanAreaSqKM,minAreaSqKM,maxAreaSqKM\n")

with open(gbOpenCSV,'w+') as f:
    headerWriter(f)

with open(gbHumCSV,'w+') as f:
    headerWriter(f)

with open(gbAuthCSV,'w+') as f:
    headerWriter(f)


for (path, dirname, filenames) in os.walk(ws["working"] + "/releaseData/"):
    print(datetime.now(), path)

    if("gbHumanitarian" in path):
        csvPath = gbHumCSV
    elif("gbOpen" in path):
        csvPath = gbOpenCSV
    elif("gbAuthoritative" in path):
        csvPath = gbAuthCSV
    else:
        continue
    
    metaSearch = [x for x in filenames if re.search('metaData.json', x)]
    if(len(metaSearch)==1):
        with open(path + "/" + metaSearch[0], encoding='utf-8', mode="r") as j:
            meta = json.load(j)
        
        isoMeta = isoDetails[isoDetails["Alpha-3code"] == meta['boundaryISO']]
        #Build the metadata
        metaLine = '"' + meta['boundaryID'] + '","' + isoMeta["Name"].values[0] + '","' + meta['boundaryISO'] + '","' + meta['boundaryYear'] + '","' + meta["boundaryType"] + '","'

        if("boundaryCanonical" in meta):
            if(len(meta["boundaryCanonical"])>0):
                metaLine = metaLine + meta["boundaryCanonical"] + '","'
            else:
                metaLine = metaLine + 'Unknown","'
        else:
            metaLine = metaLine + 'Unknown","'

        #Cleanup free-form text fields
        meta['licenseDetail'] = meta["licenseDetail"].replace(',','')
        meta['licenseDetail'] = meta["licenseDetail"].replace('\\','')
        meta['licenseDetail'] = meta["licenseDetail"].replace('"','')

        metaLine = metaLine + meta['boundarySource-1'] + '","' + meta['boundarySource-2'] + '","' + meta['boundaryLicense'] + '","' + meta['licenseDetail'] + '","' + meta['licenseSource'] + '","'
        metaLine = metaLine + meta['boundarySourceURL'] + '","' + meta['sourceDataUpdateDate'] + '","' + meta["buildUpdateDate"] + '","'
        
        
        metaLine = metaLine + isoMeta["Continent"].values[0] + '","' + isoMeta["UNSDG-region"].values[0] + '","'
        metaLine = metaLine + isoMeta["UNSDG-subregion"].values[0] + '","' 
        metaLine = metaLine + isoMeta["worldBankIncomeGroup"].values[0] + '","'

        metaLine = metaLine + "https://www.geoboundaries.org/api/gbID/" + meta['boundaryID'] + '","'

        #Calculate geometry statistics
        #We'll use the geoJSON here, as the statistics (i.e., vertices) will be most comparable
        #to other cases.
        geojsonSearch = [x for x in filenames if re.search('.geojson', x)]
        print(geojsonSearch)
        if not geojsonSearch:
            print('Error: Missing GeoJSON file!')
            continue
        
        # load as geopandas
        try:
            # local file
            with open(path + "/" + geojsonSearch[0], "r", encoding='utf-8') as g:
                geom = geopandas.read_file(g)
        except:
            # large LFS file, need to fetch from url
            # create url
            relPath = path[path.find('releaseData/'):] + "/" + geojsonSearch[0]
            url = 'https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/' + relPath
            print('Note: LFS file! Fetching from', url)
            # download as in-memory file-like stringio
            text = urllib.request.urlopen(url).read().decode('utf8')
            fobj = io.StringIO(text)
            # load from file-like stringio
            geom = geopandas.read_file(fobj)
        admCount = len(geom)
        
        vertices=[]
        
        for i, row in geom.iterrows():
            n = 0
            if(row.geometry.type.startswith("Multi")):
                for seg in row.geometry:
                    n += len(seg.exterior.coords)
            else:
                n = len(row.geometry.exterior.coords)
            
            vertices.append(n) ###
        
        # DEBUG
        if len(vertices) == 0:
            print('Error: Empty file?', geom, len(geom), vertices, len(list(geom.iterrows())) )
            continue
        
        metaLine = metaLine + str(admCount) + '","' + str(round(sum(vertices)/len(vertices),0)) + '","' + str(min(vertices)) + '","' + str(max(vertices)) + '","'

        #Perimeter Using WGS 84 / World Equidistant Cylindrical (EPSG 4087)
        lengthGeom = geom.copy()
        lengthGeom = lengthGeom.to_crs(epsg=4087)
        lengthGeom["length"] = lengthGeom["geometry"].length / 1000 #km
        
        metaLine = metaLine + str(lengthGeom["length"].mean()) + '","' + str(lengthGeom["length"].min()) + '","' + str(lengthGeom["length"].max()) + '","'

        #Area #mean min max Using WGS 84 / EASE-GRID 2 (EPSG 6933)
        areaGeom = geom.copy()
        areaGeom = areaGeom.to_crs(epsg=6933)
        areaGeom["area"] = areaGeom['geometry'].area / 10**6 #sqkm

        metaLine = metaLine + str(areaGeom['area'].mean()) + '","' + str(areaGeom['area'].min()) + '","' + str(areaGeom['area'].max()) + '","'
        #Cleanup
        metaLine = metaLine + '"\n'
        metaLine = metaLine.replace("nan","")

        with open(csvPath, mode='a', encoding='utf-8') as f:
            f.write(metaLine)
    

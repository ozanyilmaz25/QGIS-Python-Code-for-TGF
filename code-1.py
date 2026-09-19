import os
import numpy as np
from qgis.core import QgsMapLayerType, QgsProject, QgsWkbTypes

# CIKTI
output_dir = r"D:\Grid Factory\GRID"
output_file_path = os.path.join(output_dir, "Ondulasyon_matrix.txt")

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# VEKTOR
layer_name = "TG20"
layers = QgsProject.instance().mapLayersByName(layer_name)

if not layers:
    raise ValueError(
        f"'{layer_name}' isimli katman projede bulunamadı! Lütfen katman ismini kontrol edin."
    )

layer = layers[0]

if layer.geometryType() != QgsWkbTypes.PointGeometry:
    raise ValueError(f"'{layer_name}' katmanı bir nokta katmanı değil!")

# EPSG
crs = layer.crs()
qgis_epsg_code = crs.postgisSrid() if crs.isValid() else 4326

# ONDULASYON
lats = set()
lons = set()
points_data = {}

field_name = "Ondulasyon"
field_index = layer.fields().indexOf(field_name)

if field_index == -1:
    for idx, field in enumerate(layer.fields()):
        if field.name().lower() == field_name.lower():
            field_index = idx
            break

if field_index == -1:
    raise ValueError(
        f"Katmanın öznitelik tablosunda '{field_name}' isimli sütun bulunamadı!"
    )

for feature in layer.getFeatures():
    geom = feature.geometry()
    if not geom or geom.isEmpty():
        continue

    pt = geom.asPoint()
    lon = round(pt.x(), 6)
    lat = round(pt.y(), 6)

    val_attr = feature.attribute(field_index)
    try:
        val = float(val_attr)
    except (ValueError, TypeError):
        val = -9999.0000

    lats.add(lat)
    lons.add(lon)
    points_data[(lat, lon)] = val

# KOORDINATLAR VE GRID PARAMETRELERI
sorted_lats = sorted(list(lats), reverse=True)  # Kuzeyden Güneye (N-to-S)
sorted_lons = sorted(list(lons))  # Batıdan Doğuya (W-to-E)

nrows = len(sorted_lats)
ncols = len(sorted_lons)

lat_north = sorted_lats[0]
lat_south = sorted_lats[-1]
lon_west = sorted_lons[0]
lon_east = sorted_lons[-1]

delta_lat_deg = (
    abs(sorted_lats[0] - sorted_lats[1]) if nrows > 1 else 0.01666667
)
delta_lon_deg = (
    abs(sorted_lons[1] - sorted_lons[0]) if ncols > 1 else 0.01666667
)


# HASSAS DMS DONUSUM
def deg_to_dms_precise(deg):
    deg_abs = abs(deg)
    d = int(deg_abs)
    remainder = (deg_abs - d) * 60.0
    m = int(remainder)
    s = (remainder - m) * 60.0

    if round(s, 4) >= 60.0:
        s = 0.0
        m += 1
    if m >= 60:
        m = 0
        d += 1

    return f"{d:02d} {m:02d} {s:07.4f}"


# DD MM SS
def deg_to_dms_standard(deg):
    d = int(deg)
    m = int(round((deg - d) * 60))
    s = 0
    if m == 60:
        d += 1
        m = 0
    return f"{d:02d} {m:02d} {s:02d}"


# MATRIS
data_matrix = np.full((nrows, ncols), -9999.0000)
missing_points = []
point_counter = 0

for i, lat in enumerate(sorted_lats):
    for j, lon in enumerate(sorted_lons):
        point_counter += 1
        if (lat, lon) in points_data and points_data[(lat, lon)] != -9999.0000:
            data_matrix[i, j] = points_data[(lat, lon)]
        else:
            missing_points.append(
                {
                    "index": point_counter,
                    "row": i + 1,
                    "col": j + 1,
                    "lat": lat,
                    "lon": lon,
                }
            )

# S-to-N
data_matrix = np.flipud(data_matrix)

# ANALIZ MESAJI
print("\n" + "=" * 65)
print("GRID VE KOORDINAT ANALIZI SONUCLARI")
print("=" * 65)

print("\n--- KOORDINAT VE GRID ADIM (SS.0000) ---")
print(f" • Katman EPSG Kodu: {qgis_epsg_code}")
print(f" • Lat Min: {deg_to_dms_precise(lat_south)}")
print(f" • Lat Max: {deg_to_dms_precise(lat_north)}")
print(f" • Lon Min: {deg_to_dms_precise(lon_west)}")
print(f" • Lon Max: {deg_to_dms_precise(lon_east)}")
print(f" • Delta Lat: {deg_to_dms_precise(delta_lat_deg)}")
print(f" • Delta Lon: {deg_to_dms_precise(delta_lon_deg)}")

print("\n--- VERI DENETIM ---")
print(f" • Grid Boyutu        : {nrows} Satır x {ncols} Sütun")
print(f" • Toplam Grid Noktası: {point_counter} adet")

if missing_points:
    print(
        f"\n UYARI: Toplam {len(missing_points)} adet EKSİK / BOŞ nokta tespit edildi!"
    )
    print("-" * 65)
    for p in missing_points[:15]:
        print(
            f"  • Nokta No: {p['index']:<5} | Satır: {p['row']:<3} Sütun: {p['col']:<3} | Enlem: {deg_to_dms_precise(p['lat'])}, Boylam: {deg_to_dms_precise(p['lon'])}"
        )
    if len(missing_points) > 15:
        print(f"  ... ve {len(missing_points) - 15} adet daha eksik nokta var.")
else:
    print("\n: Grid üzerindeki tüm noktalarda ondulasyon değeri mevcut.")

print("=" * 65 + "\n")

# ISG FORMAT
header_text = f"""model name : TG-20 (1-min Point Matrix)
model year : 2020
model type : hybrid geoid
data unit  : m
ellipsoid  : GRS80
frame/epoch: ITRF96 (2005.0)
height dat.: TUDKA-99
tide system: zero-tide
EPSG code  : 7907
lat min    : {deg_to_dms_standard(lat_south)}
lat max    : {deg_to_dms_standard(lat_north)}
lon min    : {deg_to_dms_standard(lon_west)}
lon max    : {deg_to_dms_standard(lon_east)}
delta lat  : {deg_to_dms_standard(delta_lat_deg)}
delta lon  : {deg_to_dms_standard(delta_lon_deg)}
nrows      : {nrows}
ncols      : {ncols}
nodata val : -9999.0000
data order : S-to-N, W-to-E
citation   : H. Yildiz et al. (2020). The Turkish hybrid geoid: TG-20. V. 1.0. GFZ Data Services. http://doi.org/10.5880/isg.2020.011
--------------------------------------------------------------------------------
"""

with open(output_file_path, "w", encoding="utf-8") as f:
    f.write(header_text)
    for row in range(nrows):
        row_str = " ".join([f"{val:9.4f}" for val in data_matrix[row, :]])
        f.write(row_str + "\n")

print(f"Çıktı dosyası oluşturuldu: {output_file_path}")
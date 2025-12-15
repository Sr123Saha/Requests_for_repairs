import zipfile

with zipfile.ZipFile("TZ.zip", "r") as zip_ref:
    zip_ref.extractall("TZ_no_zip")
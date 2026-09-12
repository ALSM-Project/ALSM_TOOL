# Overview

This repository contains Python scripts for converting BMS and DSPF files to React and Java code.

## Files

- **bms2code.py:** Converts BMS files to React and Java code.
- **bms2react.py:** Converts BMS files to React code only.
- **dspf2code.py:** Converts DSPF files to React and Java code.
- **dspf2react.py:** Converts DSPF files to React code only.

# Usage

## General Usage

1. Open a terminal window.
2. Navigate to the directory containing the script you want to use.
3. Run the script using the following command:

    ```bash
    python <script_name>.py <arguments>
    ```

    Replace `<script_name>` with the actual name of the script (e.g., `bms2react.py`) and provide the required arguments.

## Specific Scripts

### bms2code.py

```bash
python bms2code.py -bms <path_to_BMS_folder> -react <path_to_React_folder> -spring <path_to_Spring_folder> -package <Spring_package>
```
- **path_to_BMS_folder** Path to the BMS folder. Converts BMS files to React and Java code.
- **path_to_React_folder** Path to the React folder. Converts BMS files to React code only.
- **path_to_Spring_folder** Path to the Spring folder (e.g., "C:/spring-project"). Converts DSPF files to React and Java code.
- **Spring_package** Path to the Spring package (e.g., "fa.training"). Converts DSPF files to React and Java code.

### bms2react.py

```bash
python bms2react.py -bms <path_to_BMS_folder> -react <path_to_React_folder> 
```
- **path_to_BMS_folder** Path to the BMS folder. Converts BMS files to React code.
- **path_to_React_folder** Path to the React folder. Converts BMS files to React code only.

### dspf2code.py

```bash
python dspf2code.py -dspf <path_to_DSPF_folder> -react <path_to_React_folder> -spring <path_to_Spring_folder> -package <Spring_package>
```
- **path_to_DSPF_folder** Path to the DSPF folder. Converts DSPF files to React and Java code.
- **path_to_React_folder** Path to the React folder. Converts DSPF files to React code only.
- **path_to_Spring_folder** Path to the Spring folder (e.g., "C:/spring-project"). Converts DSPF files to React and Java code.
- **Spring_package** Path to the Spring package (e.g., "fa.training"). Converts DSPF files to React and Java code.


### dspf2react.py

```bash
python dspf2react.py -bms <path_to_DSPF_folder> -react <path_to_React_folder> 
```
- **path_to_DSPF_folder** Path to the DSPF folder. Converts DSPF files to React code.
- **path_to_React_folder** Path to the React folder. Converts DSPF files to React code only.
---
##### Notice:
``` 
**Revert to commit 4312e911 "generate function comment for python converter file" for react conversion without api call in frontend**
```
- Should replace ```if "name" in item and item["name"] and "type" in item and item["type"] in {'O', 'B'}``` to ```if "name" in item and item["name"] and "type" in item and item["type"] in {'I', 'B'}``` for correct output
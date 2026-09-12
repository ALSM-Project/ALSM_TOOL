'''
bms2react.py

This script converts BMS files into corresponding React components. It parses BMS files, extracts information about map items, and generates React components based on the extracted data.

Author: KhangNV19
Date: 2024-01-15
'''
import argparse
import os
import re
import json


def get_value(search_result):
    """
    Extracts the value from a search result string.

    Parameters:
    - search_result (str): The input search result string.

    Returns:
    - str or list: The extracted value.
    """
    value = ""
    if search_result.find("=") == -1:
        find_match = re.compile(r"'(.*?)'").search(search_result)
        if find_match:
            value = find_match.group(0)
    elif not search_result.find(")") == -1:
        value = (
            search_result[search_result.find("=") + 1 :]
            .replace("(", "")
            .replace(")", "")
            .split(",")
        )
    elif search_result.find(")") == -1:
        value = search_result[search_result.find("=") + 1 :]
    if value[0] == "'" and value[-1] == "'":
        value = value.removeprefix("'").removesuffix("'")
    return value


def extract_property(current_item):
    """
    Extracts properties from a given item in the map file.

    Parameters:
    - current_item (str): The input map item string.

    Returns:
    - dict: Dictionary containing extracted properties.
    """
    pattern_type = re.compile(r"TYPE\s*=\s*([A-Z]+)")
    pattern_mode = re.compile(r"MODE\s*=\s*([A-Z]+)")
    pattern_lang = re.compile(r"LANG\s*=\s*([A-Z]+)")
    pattern_storage = re.compile(r"STORAGE\s*=\s*(?:\(([A-Z,]+)\)|([A-Z]+))")
    pattern_ctrl = re.compile(r"CTRL\s*=\s*(?:\(([A-Z,]+)\)|([A-Z]+))")
    pattern_term = re.compile(r"TERM\s*=\s*([A-Za-z0-9]+)")
    pattern_tioapfx = re.compile(r"TIOAPFX\s*=\s*([A-Z]+)")
    pattern_pos = re.compile(r"POS=\((\d+),(\d+)\)")
    pattern_length = re.compile(r"LENGTH=(\d+)")
    pattern_initial = re.compile(r"INITIAL=\'.*\'", re.DOTALL)
    pattern_title = re.compile(r"TITLE \'.*\'", re.DOTALL)
    pattern_title = re.compile(r"TITLE \'(.+?)\'")
    pattern_color = re.compile(r"COLOR\s*=\s*([A-Za-z0-9]+)")
    pattern_occurs = re.compile(r"OCCURS\s*=\s*([0-9]+)")
    pattern_mapatts = re.compile(r"MAPATTS\s*=\s*(?:\(([A-Z,]+)\)|([A-Z]+))")
    pattern_attrb = re.compile(r"ATTRB\s*=\s*(?:\(([A-Z,]+)\)|([A-Z]+))")
    data = {}
    current_item = current_item.replace(" = ", "=")
    if re.match(r"\s*DFHM\w+\s+", current_item):
        data["define"] = (
            re.match(r"\s*DFHM\w+\s+", current_item).group(0).replace(" ", "")
        )

    elif re.match(r"\s*([A-Z0-9]+)\s+DFHM\w+\s+", current_item):
        original_list = (
            re.match(r"\s*([A-Z0-9]+)\s+DFHM\w+\s+", current_item).group(0).split(" ")
        )
        filtered_list = [value for value in original_list if value.strip()]
        data["name"] = filtered_list[0]
        data["define"] = filtered_list[1]
    if pattern_title.search(current_item):
        search = pattern_title.search(current_item).group(0)
        data["title"] = get_value(search)
    if pattern_type.search(current_item):
        search = pattern_type.search(current_item).group(0)
        data["type"] = get_value(search)
    if pattern_mode.search(current_item):
        search = pattern_mode.search(current_item).group(0)
        data["mode"] = get_value(search)
    if pattern_lang.search(current_item):
        search = pattern_lang.search(current_item).group(0)
        data["lang"] = get_value(search)
    if pattern_storage.search(current_item):
        search = pattern_storage.search(current_item).group(0)
        data["storage"] = get_value(search)
    if pattern_ctrl.search(current_item):
        search = pattern_ctrl.search(current_item).group(0)
        data["ctrl"] = get_value(search)
    if pattern_term.search(current_item):
        search = pattern_term.search(current_item).group(0)
        data["term"] = get_value(search)
    if pattern_tioapfx.search(current_item):
        search = pattern_tioapfx.search(current_item).group(0)
        data["tioapfx"] = get_value(search)
    if pattern_pos.search(current_item):
        search = pattern_pos.search(current_item).group(0)
        data["pos"] = get_value(search)
    if pattern_length.search(current_item):
        search = pattern_length.search(current_item).group(0)
        data["length"] = get_value(search)
    if pattern_initial.search(current_item):
        search = pattern_initial.search(current_item).group(0)
        start_with_uppercase_pattern = re.compile(r"\*+\s*[A-Z]+")
        start_with_lowercase_pattern = re.compile(r"\*+\s*[a-z.]+")
        if start_with_lowercase_pattern.search(current_item):
            data["initial"] = re.sub(r"(\s*)(\*+)(\s*)", r"", get_value(search))
        elif start_with_uppercase_pattern.search(current_item):
            data["initial"] = re.sub(r"(\s*)(\*+)(\s*)", r" ", get_value(search))
    if pattern_mapatts.search(current_item):
        search = pattern_mapatts.search(current_item).group(0)
        data["mapatts"] = get_value(search)
    if pattern_attrb.search(current_item):
        search = pattern_attrb.search(current_item).group(0)
        data["attrb"] = get_value(search)
    else:
        pattern_attrb = re.compile(r"ATTRB\s*=\s*([A-Za-z0-9]+)")
        if pattern_attrb.search(current_item):
            search = pattern_attrb.search(current_item).group(0)
            data["attrb"] = get_value(search)
    if pattern_color.search(current_item):
        search = pattern_color.search(current_item).group(0)
        data["color"] = get_value(search)
    if pattern_occurs.search(current_item):
        search = pattern_occurs.search(current_item).group(0)
        data["occurs"] = get_value(search)
    return data


def extract_map_items(file_path):
    """
    Extracts map items from a given map file.

    Parameters:
    - file_path (str): The path to the map file.

    Returns:
    - list: List of dictionaries containing extracted map items.
    """
    map_items = []
    with open(file_path, "r", encoding="utf8") as file:
        current_item = ""
        new_item = ""
        for index, line in enumerate(file):
            if re.match(r"\s*DFHM\w+\s+", line):
                new_item += line
            elif re.match(r"\s*([A-Z0-9]+)\s+DFHM\w+\s+", line):
                new_item += line
            else:
                current_item += line
            if new_item or (re.match(r"\s*END\s*", line) is not None):
                data = extract_property(current_item)
                map_items.append(data)
                current_item = new_item
                new_item = ""
        # data = extract_property(current_item)
        # map_items.append(data)
        file.close()
    return map_items


def convert_dfhmsd(define_data):
    """
    Converts DFHMSD define data to React code.

    Parameters:
    - define_data (dict): Dictionary containing DFHMSD define data.

    Returns:
    - str: React code for DFHMSD.
    """
    if "type" in define_data:
        if define_data["type"] == "FINAL":
            return ""
    title = define_data["title"] if "title" in define_data else ""
    react_code = f"""
    <Helmet>
        <title>{title if title else "Untitle"}</title>
    </Helmet>
    """
    return react_code


def convert_dfhmdi(define_data):
    """
    Converts DFHMDI define data to React code.

    Parameters:
    - define_data (dict): Dictionary containing DFHMDI define data.

    Returns:
    - str: React code for DFHMDI.
    """
    react_code = ""
    return react_code


def convert_dfhmdf_input(define_data):
    """
    Converts DFHMDF define data to React code.

    Parameters:
    - define_data (dict): Dictionary containing DFHMDF define data.

    Returns:
    - str: React code for DFHMDF.
    """
    col = int(define_data["pos"][1])
    row = int(define_data["pos"][0])
    max_length = f'maxLength={{{int(define_data["length"])}}}'
    tsx_id = ""
    tsx_name = ""
    on_change_function = ""
    on_keydown_function = ""
    color = (
        f'styles={{{{color:"{define_data["color"].lower()}"}}}}'
        if "color" in define_data
        else ""
    )

    tsx_type = f'type=\'{"number" if "NUM" in define_data["attrb"] else "text"}\''
    disabled = "disabled" if "PROT" in define_data["attrb"] else ""

    if "name" in define_data:
        tsx_id = f'name=\'{define_data["name"]}\''.lower()
        tsx_name = f'id=\'{define_data["name"]}\''.lower()
        if not disabled and "ASKIP" not in define_data["attrb"]:
            on_change_function = "onChange={handleInputChange}"
            on_keydown_function = "onKeyDown={handleSubmit}"
    tag = f"<Input {max_length} {tsx_id} {tsx_name} {tsx_type} {color} {disabled} {on_change_function} {on_keydown_function}/>"

    react_code = f"""
<GridItem col={{{col}}} row={{{row}}}>
    {tag}
</GridItem>
    """
    return react_code


def convert_dfhmdf_label(define_data):
    """
    Converts DFHMDF define data to React code.

    Parameters:
    - define_data (dict): Dictionary containing DFHMDF define data.

    Returns:
    - str: React code for DFHMDF.
    """
    col = int(define_data["pos"][1])
    row = int(define_data["pos"][0])
    initial = define_data["initial"] if "initial" in define_data else ""
    color = (
        f'style={{{{color:"{define_data["color"].lower()}"}}}}'
        if "color" in define_data
        else ""
    )
    occurs = ""
    current_row = row
    for index in range(int(define_data.get("occurs", 0))):
        current_row += 1
        occurs += f"""
<GridItem col={{{col}}} row={{{current_row}}}>
    <label> {f"{{receivedData.{define_data.get('name').lower()} }}" if define_data.get("name") else " "} </label>
</GridItem>
"""

    tag = f"<label {color}>"
    end_tag = "</label>"
    react_code = f"""
<GridItem col={{{col}}} row={{{row}}}>
    {tag}
         {f"{{receivedData.{define_data.get('name').lower()} }}" if define_data.get("name") else initial} 
    {end_tag}
</GridItem>
{occurs}
    """
    return react_code


def convert_dfhmdf(define_data):
    """
    Converts DFHMDF define data to React code.

    Parameters:
    - define_data (dict): Dictionary containing DFHMDF define data.

    Returns:
    - str: React code for DFHMDF.
    """
    if ("attrb" in define_data and "UNPROT" in define_data["attrb"]) or (
        "attrb" in define_data and "IC" in define_data["attrb"]
    ):
        return convert_dfhmdf_input(define_data)
    elif (
        "initial" in define_data
        or ("attrb" in define_data and "PROT" in define_data["attrb"])
        or ("attrb" in define_data and "ASKIP" in define_data["attrb"])
    ):
        return convert_dfhmdf_label(define_data)
    else:
        return convert_dfhmdf_input(define_data)


def convert_react_items(map_items):
    """
    Converts a list of map items to React code.

    Parameters:
    - map_items (list): List of dictionaries containing map items.

    Returns:
    - list: List of React code strings.
    """
    react_items = []
    for map_item in map_items:
        if "define" in map_item:
            define_data = map_item["define"]
            converted_item = ""
            if define_data == "DFHMSD":
                converted_item = convert_dfhmsd(map_item)
            elif define_data == "DFHMDI":
                converted_item = convert_dfhmdi(map_item)
            elif define_data == "DFHMDF":
                converted_item = convert_dfhmdf(map_item)
            else:
                converted_item = f"Unsupported define: {define_data}"
            react_items.append(converted_item)
    return react_items


def combine_rsx_code(react_items, component_name, component_data):
    """
    Combines React code items into a complete React component.

    Parameters:
    - react_items (list): List of React code items.
    - component_name (str): Name of the React component.

    Returns:
    - str: Complete React component code.
    """
    react_items = "".join(react_items)
    react_component = f"""
import {{ type ChangeEvent, useState, type KeyboardEvent }} from 'react';
import {{ Helmet }} from 'react-helmet';
import axios from 'axios';
import httpConfig from '../../config/httpConfig';

import {{ GridItem }} from '../../components/GridSystem';
import Input from '../../components/Input';

export default function {component_name}() {{
    {component_data}
  return (
    <>
     {react_items}
    </>
  );
}}
    """.replace(
        "<title>Untitle</title>", f"<title>{component_name}</title>"
    )
    return react_component


def get_all_field_name(map_items):
    """
    Extracts and filters BMS map item fields.

    Parameters:
    - map_items (list of dict): List of dictionaries representing BMS map items.

    Returns:
    - list of dict: Filtered list of BMS map item fields.
    """
    filtered_list = [
        {
            "name": item.get("name", ""),
            "type": f'{"number" if "NUM" in item.get("attrb", []) else "text"}',
            "jtype": f'{"Integer" if "NUM" in item.get("attrb", []) else "String"}',
            **item,
        }
        for item in map_items
        if (("attrb" in item)
        and "initial" not in item
        and (
            item["attrb"]
            and "PROT" not in item["attrb"]
            and "ASKIP" not in item["attrb"]
        )
        and ("name" in item and item["name"]))
        or (("attrb" in item and "UNPROT" in item["attrb"]) or (
        "attrb" in item and "IC" in item["attrb"]))
    ]
    return filtered_list


def get_all_output_field_name(map_items):
    """
    Extracts and filters unique output fields from BMS map items.

    Parameters:
    - map_items (list of dict): List of dictionaries representing BMS map items.

    Returns:
    - list of dict: Filtered list of unique output fields.
    """
    list_input = get_all_field_name(map_items)
    exclude_values = set(item["name"] for item in list_input)
    filtered_list = [
        {
            "name": item.get("name", ""),
            "type": f'{"number" if "NUM" in item.get("attrb", []) else "text"}',
            "jtype": f'{"Integer" if "NUM" in item.get("attrb", []) else "String"}',
            **item,
        }
        for item in map_items
        if ("name" in item and item["name"]) and item.get("name") not in exclude_values
    ]
    unique_names = set()
    unique_list_of_dicts = [
        d
        for d in filtered_list
        if d["name"] not in unique_names and not unique_names.add(d["name"])
    ]
    return unique_list_of_dicts


def extract_type_data(map_items, file_name):
    """
    Extracts type data for React code generation.

    Parameters:
    - map_items (list): List of dictionaries containing map items.
    - file_name (str): Name of the React component.

    Returns:
    - str: React type and data extraction code.
    """
    input_fields = get_all_field_name(map_items)
    output_fields = get_all_output_field_name(map_items)

    react_type_input = ""
    for item in input_fields:
        react_type_input += f"{item['name'].lower()}: string,\n"
    react_type_output = ""
    for item in output_fields:
        react_type_output += f"{item['name'].lower()}: string,\n"

    react_type_input_initial = react_type_input.replace("string,", repr("") + ",")
    react_type_output_initial = ""
    for item in output_fields:
        react_type_output_initial += f"{item['name'].lower()}: { repr(item.get('initial')) if item.get('initial') else repr('')},\n"

    handle_data = f"""{""}
    const [formData, setFormData] = useState<formInput>(
    {{
        {react_type_input_initial}
    }});
    const [receivedData, setReceivedData] = useState<formOutput>(
     {{
        {react_type_output_initial}
    }});

    const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {{
    setFormData((state) => {{
        return {{
        ...state,
        [event.target.name]: event.target.value,
        }};
    }});
    }};

    const handleSubmit = async (event: KeyboardEvent<HTMLInputElement>) => {{
    if (event.key === 'Enter') {{
        for (const key in formData) {{
        if (!formData[key]) {{
            return;
        }}
        }}

        const response = await axios.post(
        httpConfig.domain + '/{file_name.capitalize()}',
        formData
        );

        setReceivedData(_state => response.data);
    }}
    }};
    """

    react_type_input = ""
    for item in input_fields:
        react_type_input += f"{item['name'].lower()}: string,\n"
    react_type_output = ""
    for item in output_fields:
        react_type_output += f"{item['name'].lower()}: string,\n"
    react_code = f"""
    type formInput = {{
        {react_type_input}
    }}

    type formOutput = {{
        {react_type_output}
    }}
    """
    return react_code + handle_data


def parse_bms_2_tsx(bms_file, tsx_file):
    """
    Parses a BMS file and generates a corresponding TSX file.

    Parameters:
    - bms_file (str): Path to the BMS file.
    - tsx_file (str): Path to the output TSX file.

    Returns:
    - dict or None: Extracted information from the BMS file.
    """
    desired_object = {}
    try:
        map_items = extract_map_items(bms_file)
        react_items = convert_react_items(map_items)
        # desired_object = next(
        #     (
        #         obj
        #         for obj in map_items
        #         if obj.get("define") == "DFHMSD" and "name" in obj
        #     ),
        #     {"name": "DefaultComponent"},
        # )
        desired_object = {
            "name": bms_file.replace(os.path.abspath(os.path.dirname(bms_file)), "")
            .replace(".bms", "")
            .replace("/", "")
            .replace("\\", "")
        }
        rsx_file_content = combine_rsx_code(
            react_items,
            desired_object["name"],
            extract_type_data(map_items, desired_object["name"]),
        )
        with open(f"{tsx_file}", "w", encoding="utf8") as file:
            file.write(rsx_file_content)
        file.close()
    except Exception as ex:
        print(ex)
        return None
    return desired_object


def process_file_bms(bms_file, bms_directory, react_directory):
    """
    Processes a BMS file and generates a corresponding React component.

    Parameters:
    - bms_file (str): Path to the BMS file.
    - bms_directory (str): Path to the BMS directory.
    - react_directory (str): Path to the React directory.

    Returns:
    - dict or None: Extracted information from the BMS file.
    """
    react_path = bms_file.replace(f"{bms_directory}", f"{react_directory}")
    tsx_file = os.path.splitext(react_path)[0] + ".tsx"
    tsx_directory = os.path.dirname(tsx_file)
    os.makedirs(tsx_directory, exist_ok=True)
    tsx = parse_bms_2_tsx(bms_file, tsx_file)
    if not tsx:
        print(f"\033[91m{bms_file}\033[0m")
    return tsx


def export_react_router(dfhmsd, tsx_directory):
    """
    Exports a React router file based on DFHMSD data.

    Parameters:
    - dfhmsd (list): List of dictionaries containing DFHMSD data.
    - tsx_directory (str): Path to the TSX directory.

    Returns:
    - bool: True if successful, False otherwise.
    """
    dfhmsd = [value for value in dfhmsd if value is not None]
    try:
        router_file = os.path.join(tsx_directory, "bmsRoutes.tsx")
        react_import = []
        react_export = []
        for item in dfhmsd:
            react_export.append({"name": item["name"], "component": f'{item["name"]}'})
            react_import.append(f'import {item["name"]} from "./{item["name"]}"')
        output_str = json.dumps(react_export, separators=(",", ":"))
        react_import = "\n".join(react_import)
        react_code = f"""
import {{ type ElementType }} from 'react';
{react_import}

type BMSRoutes = {{
  name: string;
  component: ElementType;
}}[];

const bmsRoutes: BMSRoutes = {output_str};

export default bmsRoutes;
"""
        react_code = re.sub(r'"component":"([^"]+)"', r"component:\1", react_code)
        react_code = re.sub(r'"name":"([^"]+)"', r'name:"\1"', react_code)
        with open(router_file, "w") as tsx_file:
            tsx_file.write(f"{react_code}")
    except Exception as ex:
        print(ex)
        return False
    return True


def export_react_router_from_dir(tsx_directory):
    """
    Exports a React router file from a directory of TSX files.

    Parameters:
    - tsx_directory (str): Path to the TSX directory.

    Returns:
    - bool: True if successful, False otherwise.
    """
    tsx_files = [f for f in os.listdir(tsx_directory) if f.endswith(".tsx")]
    tsx_files = [
        f.replace(tsx_directory, "")
        .replace(".tsx", "")
        .replace("/", "")
        .replace("\\", "")
        for f in tsx_files
    ]
    tsx_files = [s for s in tsx_files if not any(c.islower() for c in s)]
    tsx_files = [{"name": f} for f in tsx_files]
    return export_react_router(tsx_files, tsx_directory)


def list_file_in_input_source(bms_directory, react_directory):
    """
    Lists and processes BMS files in the input source.

    Parameters:
    - bms_directory (str): Path to the BMS directory.
    - react_directory (str): Path to the React directory.
    """
    dfhmsd_list = []
    if not os.path.exists(bms_directory):
        print(f"\033[91mBMS directory '{bms_directory}' does not exist.\033[0m")
        return
    if not os.path.exists(react_directory):
        os.makedirs(react_directory)
    bms_files = []
    for root, dirs, files in os.walk(bms_directory, followlinks=False):
        for file in files:
            if file.endswith(".bms"):
                bms_files.append(os.path.join(root, file))
    for bms_file in bms_files:
        dfhmsd_list.append(process_file_bms(bms_file, bms_directory, react_directory))

    if export_react_router_from_dir(react_directory):
        print(f"\033[92mExported router name: bmsRouter.tsx\033[0m{''}")
    else:
        print(f"\033[91mUnable to export router name\033[0m{''}")


def main():
    """
    Main function to execute the BMS to React conversion.
    """
    os.system("")
    parser = argparse.ArgumentParser(
        description="Process BMS and React folders using bms2react.py"
    )
    parser.add_argument("-bms", help="Path to the BMS folder", required=True)
    parser.add_argument("-react", help="Path to the React folder", required=True)
    args = parser.parse_args()
    bms_folder = args.bms
    react_folder = args.react
    list_file_in_input_source(bms_folder, react_folder)


if __name__ == "__main__":
    main()

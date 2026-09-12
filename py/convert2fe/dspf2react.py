"""
dspf2react

This script converts DSPF (Display File) definitions into React components. 
It reads DSPF files, extracts information about the display file items, 
and generates corresponding React component code.

The conversion process includes extracting properties such as position, 
type, length, name, and title from DSPF item definitions. 
The extracted information is then used to generate React component code
for input and output fields.

Author: KhangNV19
Date: 2024-1-15
"""
import argparse
import os
import re
import json
import codecs


def get_value(search_result):
    """
    Extracts a value from a search result.

    Args:
    - search_result (str): The search result string.

    Returns:
    - str: Extracted value.
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
    Extracts properties (position, type, length, name, title) from DSPF item definitions.

    Args:
    - current_item (str): DSPF item definition string.

    Returns:
    - dict: Dictionary containing extracted properties.
    """
    data = {}
    line = re.sub(r"A\*{0,1}\s{1,2}\d*\s+", "A         ", current_item)
    pattern_case_just_position_and_value = re.compile(r"A\*{0,1}\s+\d+\s{1,2}\d+")
    if pattern_case_just_position_and_value.search(current_item):
        pattern = re.compile(r"\s+\d+\s{1,2}\d+")
        result = pattern.search(line)
        final_result = (
            [
                position
                for position in result.group(0).strip().split(" ")
                if not position == ""
            ]
            if result
            else None
        )
        data["pos"] = final_result

        pattern = re.compile(r"\d+\s{0,3}\'.*\'", re.DOTALL)
        result = pattern.search(line)
        final_result = (
            re.sub(
                r"[\n\r\+\-\']",
                "",
                re.sub("\\d*'", "", re.sub(r"\s*A\*{0,1}\s+", "", result.group(0))),
            )
            if result
            else None
        )
        data["title"] = final_result
    else:
        pattern = re.compile(r"\s+\d+\s{1,2}\d+")
        result = pattern.search(line)
        final_result = (
            [
                position
                for position in result.group(0).strip().split(" ")
                if not position == ""
            ]
            if result
            else None
        )
        data["pos"] = final_result

        pattern = re.compile(r"\s+\d*[BIO\s]\s+\d+\s{1,2}\d+")
        result = pattern.search(line)
        final_result = (
            re.sub(r"\s+\d+\s{1,2}\d+", "", result.group(0)).strip() if result else None
        )
        data["type"] = (
            re.sub(r"[^IOB]", "", str(final_result))
            if not re.sub(r"[^IOB]", "", str(final_result)) == ""
            else None
        )

        pattern = re.compile(r"\s+[0-9]*[A-Z]*\s+\d*[BIO\s]\s+\d+\s{1,2}\d+")
        result = pattern.search(line)
        final_result = (
            re.sub(r"\s+\d*[BIO\s]\s+\d+\s{1,2}\d+", "", result.group(0).strip())
            if result
            else None
        )
        data["length"] = (
            re.sub(r"[^0-9]", "", str(final_result))
            if not re.sub(r"[^0-9]", "", str(final_result)) == ""
            else None
        )

        pattern = re.compile(r"\s+[0-9]*[A-Z]*\s+\d*[BIO\s]\s+\d+\s{1,2}\d+")
        pattern2 = re.compile(r"A\*{0,1}\s+\d*\s+")
        result = pattern.search(line)
        result2 = pattern2.search(line)
        final_result = (
            line[result2.span()[1] if result2 else 0 : result.span()[0]]
            if result
            else None
        )
        data["name"] = final_result

        pattern = re.compile(r"\d+\s{0,3}\'.*\'", re.DOTALL)
        result = pattern.search(line)
        final_result = (
            re.sub(
                r"[\n\r\+\-\']",
                "",
                re.sub("\\d*'", "", re.sub(r"\s*A\*{0,1}\s+", "", result.group(0))),
            )
            if result
            else None
        )
        data["title"] = final_result
    return data


def extract_map_items(file_path):
    """
    Reads a DSPF file and extracts a list of DSPF item properties.

    Args:
    - file_path (str): Path to the DSPF file.

    Returns:
    - list: List of dictionaries containing DSPF item properties.
    """
    map_items = []
    # codecs.open("myfile.txt","r",encoding='utf-8')
    with codecs.open(file_path, "r", encoding="utf-8") as file:
        current_item = ""
        new_item = ""
        # while True:
        for index, line in enumerate(file):
            pattern = re.compile(r"A\*{0,1}\s+.{2,}\s{1}\d+\s+\d+.*")
            result = pattern.search(line)
            if result:
                new_item += line
            else:
                current_item += line
            if new_item:
                data = extract_property(current_item)
                map_items.append(data)
                current_item = new_item
                new_item = ""
        data = extract_property(current_item)
        map_items.append(data)
        file.close()
    return map_items


def convert_dspf_item(define_data):
    """
    Converts DSPF item properties to React component code.

    Args:
    - define_data (dict): Dictionary containing DSPF item properties.

    Returns:
    - str: Generated React component code.
    """
    try:
        react_code = ""
        tag = "input" if (define_data.get("type") in ["I", "B"]) else "label"
        col = int(define_data["pos"][1])
        row = int(define_data["pos"][0])
        tsx_id = (
            f"id='{define_data['name']}'".lower()
            if ("name" in define_data and define_data["name"])
            else ""
        )
        name = (
            f"name='{define_data['name']}'".lower()
            if ("name" in define_data and define_data["name"])
            else ""
        )
        max_length = (
            f'maxLength={{{int(define_data["length"])}}}'
            if ("length" in define_data and define_data["length"])
            else ""
        )
        # receivedData.{define_data.get('name').lower()
        initial = (
            f'value={{formData.{define_data.get("name").lower()} }}'
            if ("name" in define_data and define_data["name"])
            else ""
        )
        initial_output = (
            f"{{receivedData.{define_data.get('name').lower()} }}"
            if define_data.get("name")
            else (
                f'{define_data["title"]}'
                if ("title" in define_data and define_data["title"])
                else ""
            )
        )

        if tag == "label":
            react_code = f"""
        <GridItem col={{{col}}} row={{{row}}}>
            <label {tsx_id}>
                {initial_output}
            </label>
        </GridItem>
            """
        else:
            on_change_function = ""
            on_keydown_function = ""
            if name:
                on_change_function = "onChange={handleInputChange}"
                on_keydown_function = "onKeyDown={handleSubmit}"
            react_code = f"""
        <GridItem col={{{col}}} row={{{row}}}>
            <Input {max_length} {tsx_id} {name} {initial} {on_change_function} {on_keydown_function}/>
        </GridItem>
            """
        return react_code
    except Exception as ex:
        print(ex)
    return


def get_all_field_name(map_items):
    """
    Extracts and filters input fields from the provided map items.

    Args:
    - map_items (list of dict): List of dictionaries representing map items.

    Returns:
    - list of dict: List of dictionaries representing input fields.
    """
    filtered_list = [
        {"name": item.get("name", ""), "type": "text", "jtype": "String", **item}
        for item in map_items
        if "name" in item
        and item["name"]
        and "type" in item
        and item["type"] in {"I", "B"}
    ]
    unique_names = set()
    unique_list_of_dicts = [
        d
        for d in filtered_list
        if d["name"] not in unique_names and not unique_names.add(d["name"])
    ]
    return unique_list_of_dicts


def get_all_output_field_name(map_items):
    """
    Extracts and filters output fields from the provided map items.

    Args:
    - map_items (list of dict): List of dictionaries representing map items.

    Returns:
    - list of dict: List of dictionaries representing output fields.
    """
    filtered_list = [
        {"name": item.get("name", ""), "type": "text", "jtype": "String", **item}
        for item in map_items
        if "name" in item
        and item["name"]
        and "type" in item
        and item["type"] in {"O", "B"}
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
    Extracts type data for React components based on DSPF input and output fields.

    Args:
    - map_items (list of dict): List of dictionaries representing map items.
    - file_name (str): Name of the React component.

    Returns:
    - str: React type data for input and output fields.
    """
    input_fields = get_all_field_name(map_items)
    output_fields = get_all_output_field_name(map_items)
    react_type_input = ""
    for item in input_fields:
        react_type_input += f"{item['name'].lower()}: string,\n"
    react_type_output = ""
    for item in output_fields:
        react_type_output += f"{item['name'].lower()}: string,\n"

    react_type_input_initial = react_type_input.replace(
        "string,", (item["title"] if item.get("title") else repr("")) + ","
    )
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


def convert_react_items(map_items):
    """
    Converts a list of DSPF items to React components.

    Args:
    - map_items (list): List of dictionaries containing DSPF item properties.

    Returns:
    - list: List of generated React component codes.
    """
    react_items = []
    for map_item in map_items:
        if "pos" in map_item and map_item["pos"]:
            converted_item = convert_dspf_item(map_item)
            react_items.append(converted_item)
    return react_items


def combine_rsx_code(react_items, component_name, component_data):
    """
    Combines React component code into a complete React component file.

    Args:
    - react_items (list): List of React component codes.
    - component_name (str): Name of the React component.

    Returns:
    - str: Complete React component file code.
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
    <Helmet>
        <title>{component_name}</title>
    </Helmet>
     {react_items}
    </>
  );
}}
    """
    return react_component


def parse_dspf_2_tsx(dspf_file, tsx_file):
    """
    Parses a DSPF file and generates a corresponding React component file.

    Args:
    - dspf_file (str): Path to the DSPF file.
    - tsx_file (str): Path to the output React component file.

    Returns:
    - dict: Information about the generated React component.
    """
    desired_object = {}
    try:
        map_items = extract_map_items(dspf_file)
        react_items = convert_react_items(map_items)
        desired_object = {
            "name": dspf_file.replace(os.path.abspath(os.path.dirname(dspf_file)), "")
            .replace(".dspf", "")
            .replace("/", "")
            .replace("\\", "")
        }
        rsx_file_content = combine_rsx_code(
            react_items,
            desired_object["name"],
            extract_type_data(map_items, desired_object["name"]),
        )
        with codecs.open(f"{tsx_file}", "w", encoding="utf-8") as file:
            file.write(f"{rsx_file_content}")
        file.close()
    except Exception as exception:
        print(exception)
        return None
    return desired_object


def process_file_dspf(dspf_file, dspf_directory, react_directory):
    """
    Processes a DSPF file and generates React components.

    Args:
    - dspf_file (str): Path to the DSPF file.
    - dspf_directory (str): Path to the DSPF folder.
    - react_directory (str): Path to the React folder.

    Returns:
    - dict: Information about the generated React component.
    """
    react_path = dspf_file.replace(f"{dspf_directory}", f"{react_directory}")
    tsx_file = os.path.splitext(react_path)[0] + ".tsx"
    tsx_directory = os.path.dirname(tsx_file)
    os.makedirs(tsx_directory, exist_ok=True)
    tsx = parse_dspf_2_tsx(dspf_file, tsx_file)
    if not tsx:
        print(f"\033[91m{dspf_file}\033[0m")
    return tsx


def export_react_router(dfhmsd, tsx_directory):
    """
    Exports a React Router file based on the generated React components.

    Args:
    - dfhmsd (list): List of dictionaries containing React component information.
    - tsx_directory (str): Path to the directory containing React components.

    Returns:
    - bool: True if successful, False otherwise.
    """
    dfhmsd = [value for value in dfhmsd if value is not None]
    try:
        router_file = os.path.join(tsx_directory, "dspfRoutes.tsx")
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

type DFPSRoutes = {{
  name: string;
  component: ElementType;
}}[];

const dfpsRoutes: DFPSRoutes = {output_str};

export default dfpsRoutes;
"""
        react_code = re.sub(r'"component":"([^"]+)"', r"component:\1", react_code)
        react_code = re.sub(r'"name":"([^"]+)"', r'name:"\1"', react_code)
        with open(router_file, "w", encoding="utf8") as tsx_file:
            tsx_file.write(f"{react_code}")
    except Exception as ex:
        print(ex)
        return False
    return True


def export_react_router_from_dir(tsx_directory):
    """
    Exports React Router file from an existing directory of React components.

    Args:
    - tsx_directory (str): Path to the directory containing React components.

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


def list_file_in_input_source(dspf_directory, react_directory):
    """
    Lists and processes all DSPF files in the specified directory.

    Args:
    - dspf_directory (str): Path to the DSPF folder.
    - react_directory (str): Path to the React folder.
    """
    dfhmsd_list = []
    if not os.path.exists(dspf_directory):
        print(f"\033[91mBMS directory '{dspf_directory}' does not exist.\033[0m")
        return
    if not os.path.exists(react_directory):
        os.makedirs(react_directory)
    dspf_files = []
    for root, dirs, files in os.walk(dspf_directory, followlinks=False):
        for file in files:
            if file.endswith(".dspf"):
                dspf_files.append(os.path.join(root, file))
    for dspf_file in dspf_files:
        dfhmsd_list.append(
            process_file_dspf(dspf_file, dspf_directory, react_directory)
        )

    if export_react_router_from_dir(react_directory):
        print(f"\033[92mExported router name: dspfRouter.tsx\033[0m{''}")
    else:
        print(f"\033[91mUnable to export router name\033[0m{''}")


def main():
    """
    Main function to execute the DSPF to React conversion.
    """
    os.system("")
    parser = argparse.ArgumentParser(
        description="Process DSPF and React folders using dspf2react.py"
    )
    parser.add_argument("-dspf", help="Path to the DSPF folder", required=True)
    parser.add_argument("-react", help="Path to the React folder", required=True)
    args = parser.parse_args()
    dspf_directory = args.dspf
    react_folder = args.react
    list_file_in_input_source(dspf_directory, react_folder)


if __name__ == "__main__":
    main()

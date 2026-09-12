"""
bms2code

This script converts BMS (Basic Mapping Support) files to Java code for a Spring project. 
It involves the generation of Data Transfer Objects (DTOs), 
models, repositories, services, service implementations, and REST API classes.

The script performs the following tasks:
- Generates Java variable declarations based on provided fields.
- Creates Data Transfer Object (DTO) Java classes for responses.
- Generates Data Transfer Object (DTO) Java classes.
- Generates Java model classes.
- Creates Spring repository interfaces.
- Generates Spring service interfaces and implementation classes.
- Creates Spring REST API classes.

Author: KhangNV19
Date: 2024-01-15
"""
import argparse
import os

from bms2react import list_file_in_input_source as parse_to_react_file

from bms2react import extract_map_items


def java_variable_declaration(fields):
    """
    Generates Java variable declarations based on the provided fields.

    Parameters:
    - fields (list of dict): List of dictionaries representing fields.

    Returns:
    - str: Java variable declarations.
    """
    declaration = ""
    for field in fields:
        data_type = "Integer" if field["type"] == "number" else "String"
        declaration += f"\tprivate {data_type} {field['name'].lower()};\n"
    return declaration


def generate_dto_response(fields, file_name, spring_folder, base_package):
    """
    Generates a Data Transfer Object (DTO) Java class based on the provided fields.

    Parameters:
    - fields (list of dict): List of dictionaries representing fields.
    - file_name (str): Name of the Java class.
    - spring_folder (str): Path to the Spring folder.
    - base_package (str): Base package for the Spring project.
    """
    file_name = file_name.capitalize()
    output_fields = get_all_output_field_name(fields)
    dto_diretory = (
        os.path.abspath(spring_folder)
        + os.path.sep
        + "dto"
        + os.path.sep
        + "bms"
        + os.path.sep
        + "response"
    )
    if not os.path.exists(dto_diretory):
        os.makedirs(dto_diretory)
    dto_file = (
        os.path.abspath(dto_diretory) + os.path.sep + file_name + "ResponseDTO.java"
    )

    import_statement = f"""
package {base_package}.dto.bms.response;

import lombok.Data;
import lombok.Builder;

    """

    var_declaration = java_variable_declaration(output_fields)
    var_declaration += "\tprivate Integer screenIdField;"
    java_code = f"""
{import_statement}

@Data
@Builder
public class {file_name}ResponseDTO {{
{var_declaration}

}}
    """
    with open(dto_file, "w", encoding="utf8") as dto:
        dto.write(java_code)
    dto.close()


def generate_dto(fields, file_name, spring_folder, base_package):
    """
    Generates a Data Transfer Object (DTO) Java class based on the provided fields.

    Parameters:
    - fields (list of dict): List of dictionaries representing fields.
    - file_name (str): Name of the Java class.
    - spring_folder (str): Path to the Spring folder.
    - base_package (str): Base package for the Spring project.
    """
    file_name = file_name.capitalize()
    input_fields = get_all_field_name(fields)
    dto_diretory = (
        os.path.abspath(spring_folder) + os.path.sep + "dto" + os.path.sep + "bms"
    )
    if not os.path.exists(dto_diretory):
        os.makedirs(dto_diretory)
    dto_file = os.path.abspath(dto_diretory) + os.path.sep + file_name + "DTO.java"

    import_statement = f"""
package {base_package}.dto.bms;

import lombok.Data;
import lombok.Builder;

    """

    var_declaration = java_variable_declaration(input_fields)
    var_declaration += "\tprivate Integer screenIdField;"
    java_code = f"""
{import_statement}

@Data
@Builder
public class {file_name}DTO {{
{var_declaration}

}}
    """
    with open(dto_file, "w", encoding="utf8") as dto:
        dto.write(java_code)
    dto.close()


def generate_model(fields, file_name, spring_folder, base_package):
    """
    Generates a Java model class based on the provided fields.

    Parameters:
    - fields (list of dict): List of dictionaries representing fields.
    - file_name (str): Name of the Java class.
    - spring_folder (str): Path to the Spring folder.
    - base_package (str): Base package for the Spring project.
    """
    file_name = file_name.capitalize()
    input_fields = get_all_field_name(fields)
    model_diretory = (
        os.path.abspath(spring_folder) + os.path.sep + "model" + os.path.sep + "bms"
    )
    if not os.path.exists(model_diretory):
        os.makedirs(model_diretory)
    model_file = os.path.abspath(model_diretory) + os.path.sep + file_name + ".java"

    import_statement = f"""
package {base_package}.model.bms;


import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import lombok.Data;
import lombok.Builder;

    """

    var_declaration = java_variable_declaration(input_fields)
    var_declaration += "\t@Id\n"
    var_declaration += "\tprivate Integer screenIdField;"
    java_code = f"""
{import_statement}

@Entity
@Data
@Builder
public class {file_name} {{
{var_declaration}

}}
    """
    with open(model_file, "w", encoding="utf8") as model:
        model.write(java_code)
    model.close()


def generate_repo(file_name, spring_folder, base_package):
    """
    Generates a repository interface for the provided model class.

    Parameters:
    - file_name (str): Name of the Java model class.
    - spring_folder (str): Path to the Spring folder.
    - base_package (str): Base package for the Spring project.
    """
    file_name = file_name.capitalize()
    repo_diretory = (
        os.path.abspath(spring_folder)
        + os.path.sep
        + "repository"
        + os.path.sep
        + "bms"
    )
    if not os.path.exists(repo_diretory):
        os.makedirs(repo_diretory)
    repo_file = (
        os.path.abspath(repo_diretory) + os.path.sep + file_name + "Repository.java"
    )

    import_statement = f"""
package {base_package}.repository.bms;

import {base_package}.model.bms.{file_name};
import org.springframework.stereotype.Repository;
import org.springframework.data.jpa.repository.JpaRepository;

    """
    java_code = f"""
{import_statement}
@Repository
public interface {file_name}Repository extends JpaRepository<{file_name}, Integer> {{

}}
    """
    with open(repo_file, "w", encoding="utf8") as model:
        model.write(java_code)
    model.close()


def generate_service(file_name, spring_folder, base_package):
    """
    Generates a Spring service interface based on the provided fields.

    Parameters:
    - file_name (str): Name of the service interface.
    - spring_folder (str): Path to the Spring folder.
    - base_package (str): Base package for the Spring project.
    """
    file_name = file_name.capitalize()
    service_diretory = (
        os.path.abspath(spring_folder) + os.path.sep + "service" + os.path.sep + "bms"
    )
    if not os.path.exists(service_diretory):
        os.makedirs(service_diretory)
    service_file = (
        os.path.abspath(service_diretory) + os.path.sep + file_name + "Service.java"
    )
    import_statement = f"package {base_package}.service.bms;\n\n"

    java_code = f"""
{import_statement}

public interface {file_name}Service {{

}}
"""
    with open(service_file, "w", encoding="utf8") as model:
        model.write(java_code)
    model.close()


def generate_service_impl(file_name, spring_folder, base_package):
    """
    Generates a Spring service implementation based on the provided fields.

    Parameters:
    - fields (list of dict): List of dictionaries representing fields.
    - file_name (str): Name of the service implementation class.
    - spring_folder (str): Path to the Spring folder.
    - base_package (str): Base package for the Spring project.
    """
    file_name = file_name.capitalize()
    service_diretory = (
        os.path.abspath(spring_folder)
        + os.path.sep
        + "service"
        + os.path.sep
        + "bms"
        + os.path.sep
        + "impl"
    )
    if not os.path.exists(service_diretory):
        os.makedirs(service_diretory)
    service_file = (
        os.path.abspath(service_diretory) + os.path.sep + file_name + "ServiceImpl.java"
    )
    import_statement = f"package {base_package}.service.bms.impl;\n\n"
    import_statement += f"import {base_package}.service.bms.{file_name}Service;\n\n"
    import_statement += f"import {base_package}.repository.bms.{file_name}Repository;\n"
    import_statement += (
        "import org.springframework.beans.factory.annotation.Autowired;\n"
    )
    import_statement += "import org.springframework.stereotype.Service;\n"

    java_code = f"""
{import_statement}

@Service
public class {file_name}ServiceImpl implements {file_name}Service {{

    @Autowired
    private {file_name}Repository repository;

}}
"""
    with open(service_file, "w", encoding="utf8") as model:
        model.write(java_code)
    model.close()


def generate_api(fields, file_name, spring_folder, base_package):
    """
    Generates a Spring REST API class based on the provided fields.

    Parameters:
    - fields (list of dict): List of dictionaries representing fields.
    - file_name (str): Name of the REST API class.
    - spring_folder (str): Path to the Spring folder.
    - base_package (str): Base package for the Spring project.
    """
    file_name = file_name.capitalize()
    api_diretory = (
        os.path.abspath(spring_folder) + os.path.sep + "api" + os.path.sep + "bms"
    )
    if not os.path.exists(api_diretory):
        os.makedirs(api_diretory)
    api_file = os.path.abspath(api_diretory) + os.path.sep + file_name + "API.java"
    all_field_output = get_all_output_field_name(fields)
    all_fields_name = [
        item["name"].lower()
        for item in all_field_output
        if item.get("type", "") == "text"
    ]
    builder_dto = ""
    if all_fields_name:
        builder_dto = f"""{file_name}ResponseDTO.builder().{'("A").'.join(all_fields_name)}("A")."""
    all_fields_name = [
        item["name"].lower()
        for item in all_field_output
        if item.get("type", "") == "number"
    ]
    if all_fields_name:
        builder_dto += f"""{'(0).'.join(all_fields_name)}(0)."""
    builder_dto += "build()"
    import_statement = f"""
package {base_package}.api.bms;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import {base_package}.dto.bms.{file_name}DTO;
import {base_package}.dto.bms.response.{file_name}ResponseDTO;
import {base_package}.service.bms.{file_name}Service;

import java.util.ArrayList;
import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

import org.springframework.beans.factory.annotation.Autowired;
    """
    java_code = f"""
{import_statement}

@RestController
@RequestMapping("/{file_name}")
public class {file_name}API  {{

    @Autowired
    private {file_name}Service service;

    @GetMapping
    public List<{file_name}DTO> getAll() {{
        return new ArrayList<{file_name}DTO>();
    }}

    @PostMapping
    public {file_name}ResponseDTO postMethodName(@RequestBody {file_name}DTO entity) {{
        return {builder_dto};
    }}

}}
"""
    with open(api_file, "w", encoding="utf8") as model:
        model.write(java_code)
    model.close()


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


def list_file_in_input_source(bms_directory, spring_target_folder, base_package):
    """
    Lists and processes BMS files in the input source, generating Java code.

    Parameters:
    - bms_directory (str): Path to the BMS directory.
    - spring_target_folder (str): Path to the Spring target folder.
    - base_package (str): Base package for the Spring project.
    """
    bms_files = []
    for root, dirs, files in os.walk(bms_directory, followlinks=False):
        for file in files:
            if file.endswith(".bms"):
                bms_files.append(os.path.join(root, file))
    for file in bms_files:
        map_items = extract_map_items(file)
        file_name, file_extension = os.path.splitext(os.path.basename(file))
        # map_items = get_all_field_name(map_items)
        try:
            generate_dto_response(
                map_items, file_name, spring_target_folder, base_package
            )
            generate_api(map_items, file_name, spring_target_folder, base_package)
            generate_dto(map_items, file_name, spring_target_folder, base_package)
            generate_repo(file_name, spring_target_folder, base_package)
            generate_model(map_items, file_name, spring_target_folder, base_package)
            generate_service(file_name, spring_target_folder, base_package)
            generate_service_impl(
                file_name, spring_target_folder, base_package
            )
        except Exception as ex:
            print(f"\033[91mUnable to generate java code: {file}")
            print(f"==>cause: {ex}\033[0m")


def check_exist_folder(bms_folder, react_folder, spring_folder, spring_package):
    """
    Checks the existence of folders and initiates BMS to React and Java code generation.

    Parameters:
    - bms_folder (str): Path to the BMS folder.
    - react_folder (str): Path to the React folder.
    - spring_folder (str): Path to the Spring folder.
    - spring_package (str): Base package for the Spring project.
    """
    base_spring_package = spring_package
    if not os.path.exists(bms_folder):
        print(f"\033[91mBMS directory '{bms_folder}' does not exist.\033[0m")
        return
    if not os.path.exists(spring_folder):
        print(f"\033[91mBMS directory '{spring_folder}' does not exist.\033[0m")
        return
    if not os.path.exists(react_folder):
        os.makedirs(react_folder)
    spring_package = "src.main.java." + spring_package
    spring_package = spring_package.replace(".", os.path.sep)
    full_spring_target_folder = (
        os.path.abspath(spring_folder) + os.path.sep + spring_package
    )
    os.makedirs(full_spring_target_folder, exist_ok=True)
    parse_to_react_file(bms_folder, react_folder)
    list_file_in_input_source(
        bms_folder, full_spring_target_folder, base_spring_package
    )
    return


def main():
    """
    Main function to execute the BMS to React and Java code conversion.
    """
    os.system("")
    parser = argparse.ArgumentParser(
        description="Process BMS and React folders using bms2react.py"
    )
    parser.add_argument("-bms", help="Path to the BMS folder", required=True)
    parser.add_argument("-react", help="Path to the React folder", required=True)
    parser.add_argument(
        "-spring",
        help='Path to the Spring folder (Ex. "C:/spring-project")',
        required=True,
    )
    parser.add_argument(
        "-package", help='Path to the Spring package (Ex. "fa.training")', required=True
    )
    args = parser.parse_args()
    bms_folder = args.bms
    react_folder = args.react
    spring_folder = args.spring
    spring_package = args.package
    check_exist_folder(bms_folder, react_folder, spring_folder, spring_package)



if __name__ == "__main__":
    main()

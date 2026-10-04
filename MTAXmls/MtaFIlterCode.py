import xml.etree.ElementTree as ET


def filter_by_msgPartRef(root, target_value):
    """
    Keep only child nodes where msgPartRef/@value == target_value.
    Preserve overall XML structure.
    """
    for parent in root:
        children = list(parent)  # avoid modifying while iterating

        for child in children:
            msg_ref = child.find("msgPartRef")

            # Remove if:
            # - msgPartRef missing OR
            # - value doesn't match
            if msg_ref is None or msg_ref.get("value") != target_value:
                parent.remove(child)

    return root


def process_xml(input_file, output_file, msg_value):
    """
    Load XML → filter → save result
    """
    tree = ET.parse(input_file)
    root = tree.getroot()

    filter_by_msgPartRef(root, msg_value)

    tree.write(output_file, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    input_file = "format.xml"     # your input file
    output_file = "output.xml"   # filtered output
    msg_value = "TC1"            # filter value

    process_xml(input_file, output_file, msg_value)

    print(f"Filtered XML saved to {output_file}")


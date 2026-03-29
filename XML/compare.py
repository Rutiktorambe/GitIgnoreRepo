import xml.etree.ElementTree as ET

def node_to_tuple(elem):
    return (
        elem.tag,
        tuple(sorted(elem.attrib.items())),
        (elem.text or "").strip(),
        tuple(node_to_tuple(e) for e in list(elem))
    )

def remove_duplicate_nodes(xml_string, path):
    root = ET.fromstring(xml_string)

    # Navigate to the container element
    path_parts = path.split('/')
    elem = root
    for part in path_parts[1:]:  # Skip the first part (root)
        elem = elem.find(part)
        if elem is None:
            raise ValueError(f"Path not found: {part}")

    # Deduplicate based on structure
    seen = set()
    to_remove = []
    for child in list(elem):
        node_repr = node_to_tuple(child)
        if node_repr in seen:
            to_remove.append(child)
        else:
            seen.add(node_repr)

    # Remove duplicates
    for dup in to_remove:
        elem.remove(dup)

    return ET.ElementTree(root)

# ===== Example usage =====
xml_data = """<Root>
    <Quotes>
        <Quote>
            <parent>
                <Level1>
                    <Level2A>
                        <NewRisk>
                            <Level3>
                                <Variable1 value="21" />
                                <Variable2 value="42" />
                                <Vaehicles>
                                    <Vaehicle>
                                        <ID_Value value="201" />
                                        <Name_Value value="e" />
                                        <City_Value value="Mumbai" />
                                        <Pincode_Value value="400001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="202" />
                                        <Name_Value value="e" />
                                        <City_Value value="Pune" />
                                        <Pincode_Value value="411001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="203" />
                                        <Name_Value value="e" />
                                        <City_Value value="Nagpur" />
                                        <Pincode_Value value="440001" />
                                        <Region_Value value="East" />
                                    </Vaehicle>
                                </Vaehicles>
                            </Level3>
                        </NewRisk>
                        <oldRisk>
                            <Level3>
                                <Variable1 value="21" />
                                <Variable2 value="42" />
                                <Vaehicles>
                                 <Variable1 value="21" />
                                <Variable2 value="42" />
                                    <Vaehicle>
                                        <ID_Value value="301" />
                                        <Name_Value value="a" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="400001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="302" />
                                        <Name_Value value="b" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="411001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="303" />
                                        <Name_Value value="c" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="440001" />
                                        <Region_Value value="East" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="302" />
                                        <Name_Value value="b" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="411001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                      <Vaehicle>
                                        <ID_Value value="301" />
                                        <Name_Value value="a" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="400001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="302" />
                                        <Name_Value value="b" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="411001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="303" />
                                        <Name_Value value="c" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="440001" />
                                        <Region_Value value="East" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="302" />
                                        <Name_Value value="b" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="411001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                      <Vaehicle>
                                        <ID_Value value="301" />
                                        <Name_Value value="a" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="400001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="302" />
                                        <Name_Value value="b" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="411001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="303" />
                                        <Name_Value value="c" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="440001" />
                                        <Region_Value value="East" />
                                    </Vaehicle>
                                    <Vaehicle>
                                        <ID_Value value="302" />
                                        <Name_Value value="b" />
                                        <City_Value value="UnknownCity" />
                                        <Pincode_Value value="411001" />
                                        <Region_Value value="West" />
                                    </Vaehicle>
                                </Vaehicles>
                            </Level3>
                        </oldRisk>
                    </Level2A>
                    <Level2B>
                        <Variable4 value="7" />
                        <Variable5 value="14" />
                    </Level2B>
                </Level1>
                <AnotherBranch>
                    <NestedBranch>
                        <DeeperBranch>
                            <Variable6 value="100" />
                            <Variable7 value="200" />
                        </DeeperBranch>
                    </NestedBranch>
                </AnotherBranch>
            </parent>
        </Quote>
    </Quotes>
</Root>"""

# Path to container with possible duplicates
path = "Root/Quotes/Quote/parent/Level1/Level2A/oldRisk/Level3/Vaehicles"

# Remove duplicates
tree = remove_duplicate_nodes(xml_data, path)

# Save updated XML to file
tree.write("updated_output.xml", encoding="utf-8", xml_declaration=True)

# Print to console
print(ET.tostring(tree.getroot(), encoding="unicode"))

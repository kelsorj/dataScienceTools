from pymongo import MongoClient
from pyvis.network import Network
import re
import networkx as nx
from collections import Counter
import community as community_louvain


# Function to determine all unique conditions connected to nodes in the cluster
def get_all_conditions_for_cluster(cluster, nt):
    all_conditions = set()
    for node_id in cluster:
        node_conditions = {
            edge["title"]
            for edge in nt.edges
            if edge["from"] == node_id or edge["to"] == node_id
        }
        all_conditions.update(node_conditions)
    return list(all_conditions)


# Function to insert line breaks after every 50 characters, breaking at whitespace
def insert_line_breaks(string, every=50):
    lines = []
    start = 0
    while start < len(string):
        end = start + every
        if end < len(string):
            while end > start and string[end] not in [' ', '\t']:
                end -= 1
            if end == start:  # If no whitespace is found within the range
                end = start + every
        else:
            end = len(string)
        lines.append(string[start:end].strip())
        start = end
    return "\n".join(lines)


# Function to determine the most common conditions connected to nodes in the cluster
def get_top_conditions_for_cluster(cluster, nt, top_n=3):
    all_conditions = []
    for node_id in cluster:
        node_conditions = [
            edge["title"]
            for edge in nt.edges
            if edge["from"] == node_id or edge["to"] == node_id
        ]
        all_conditions.extend(node_conditions)

    counter = Counter(all_conditions)
    top_conditions = counter.most_common(top_n)
    return [condition[0] for condition in top_conditions]


# Function to determine the common conditions shared by all nodes in a cluster
def get_shared_conditions_for_cluster(cluster, nt):
    shared_conditions = None
    for node_id in cluster:
        node_conditions = set(
            edge["title"]
            for edge in nt.edges
            if edge["from"] == node_id or edge["to"] == node_id
        )
        if shared_conditions is None:
            shared_conditions = node_conditions
        else:
            shared_conditions.intersection_update(node_conditions)
    return shared_conditions


# Function to calculate centroid of a cluster
def compute_cluster_centroid(cluster, network):
    x_coords = [network.get_node(node)["x"] for node in cluster]
    y_coords = [network.get_node(node)["y"] for node in cluster]
    centroid_x = sum(x_coords) / len(x_coords)
    centroid_y = sum(y_coords) / len(y_coords)
    return (centroid_x, centroid_y)


def add_cluster_title_node(cluster_nodes, title, network):
    """
    Add a title node at the centroid of a cluster.

    Args:
    - cluster_nodes (list): List of node ids that belong to the cluster.
    - title (str): Label for the title node.
    - network (pyvis.network.Network): The network object.

    Returns:
    - Updated network object.
    """
    x_coords = [network.get_node(node)["x"] for node in cluster_nodes]
    y_coords = [network.get_node(node)["y"] for node in cluster_nodes]

    # Calculate centroid
    centroid_x = sum(x_coords) / len(x_coords)
    centroid_y = sum(y_coords) / len(y_coords)

    # Add the title node
    network.add_node(
        title, x=centroid_x, y=centroid_y, shape="box", color="red", title=title
    )

    return network


def recursive_search(record, keys):
    """
    Recursively searches for a sequence of keys in a nested dictionary.
    """
    if not keys or not isinstance(record, dict):
        return None

    # If the first key exists in the record, and there are no more keys left, return its value
    if keys[0] in record and len(keys) == 1:
        return record[keys[0]]

    # If the first key exists and there are more keys, search deeper
    if keys[0] in record:
        return recursive_search(record[keys[0]], keys[1:])

    return None


def create_hover_text(record):
    # Extract the LastUpdatePostDate
    last_update = (
        recursive_search(
            record,
            [
                "FullStudy",
                "Study",
                "StatusModule",
                "LastUpdatePostDateStruct",
                "LastUpdatePostDate",
            ],
        )
        or "N/A"
    )

    # Extract brief title
    brief_title = (
        recursive_search(
            record,
            [
                "FullStudy",
                "Study",
                "ProtocolSection",
                "IdentificationModule",
                "BriefTitle",
            ],
        )
        or "N/A"
    )

    # Extract brief summary
    brief_summary = (
        recursive_search(
            record, ["FullStudy", "Study", "DescriptionModule", "BriefSummary"]
        )
        or "N/A"
    )

    # Extract conditions
    conditions = get_conditions(record)
    conditions_str = ", ".join(conditions) if conditions else "N/A"

    # Extract all http addresses and format them as links (if this is supported by the rendering engine)
    http_links = re.findall(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        str(record),
    )
    links_str = (
        "<br>".join(
            [f'<a href="{link}" target="_blank">{link}</a>' for link in http_links]
        )
        if http_links
        else "N/A"
    )

    # Combine everything with provided titles and HTML line breaks
    hover_text = f"Last update: {last_update}<br>Brief title: {brief_title}<br>Brief summary: {brief_summary}<br>Conditions: {conditions_str}<br>Links:<br>{links_str}"

    return hover_text


def extract_conditions(obj):
    """Recursively search for the 'Condition' field in the nested dictionary."""
    if isinstance(obj, dict):
        if "Condition" in obj:
            conditions = obj["Condition"]
            if isinstance(conditions, str):
                return [conditions]
            return conditions
        for key, value in obj.items():
            result = extract_conditions(value)
            if result:
                return result
    return []


def get_conditions(record):
    return extract_conditions(record)


# Connect to MongoDB and Fetch Data:
client = MongoClient("localhost", 27017)
db = client.mydb
collection = db.AllAPIJSON

# Retrieve a random 1000 records
all_records = list(collection.aggregate([{"$sample": {"size": 1000}}]))

# Create a dictionary to count occurrences of each OrgFullName
org_counts = {}
for record in all_records:
    org_name = record["FullStudy"]["Study"]["ProtocolSection"]["IdentificationModule"][
        "Organization"
    ]["OrgFullName"]
    if org_name in org_counts:
        org_counts[org_name] += 1
    else:
        org_counts[org_name] = 1

# Draw everything on the graph with filter menu enabled:
nt = Network(
    height="750px",
    width="100%",
    bgcolor="#222222",
    font_color="white",
    filter_menu=True,
)
nt.options = {
    "physics": {
        "enabled": True,
        "barnesHut": {
            "gravitationalConstant": -1500,  # adjusted from -2000
            "centralGravity": 0.5,  # adjusted from 0.3
            "springLength": 95,
            "springConstant": 0.03,  # adjusted from 0.04
            "damping": 0.2,  # adjusted from 0.09
            "avoidOverlap": 0.1,
        },
        "maxVelocity": 50,  # adjusted from 146
        "minVelocity": 0.1,
        "solver": "barnesHut",
        "adaptiveTimestep": True,
    }
}


# Add nodes to the graph
for record in all_records:
    node_id = str(record["_id"])
    node_label = (
        record.get("FullStudy", {})
        .get("Study", {})
        .get("ProtocolSection", {})
        .get("IdentificationModule", {})
        .get("Organization", {})
        .get("OrgFullName", "N/A")
    )
    node_hover_text = create_hover_text(record)
    organization_name = node_label
    node_size = org_counts[organization_name]
    nt.add_node(
        node_id,
        label=organization_name,
        title=node_hover_text,
        organization=organization_name,
        size=node_size,
    )

# Add edges between nodes that share the same conditions
for i, record1 in enumerate(all_records):
    for j, record2 in enumerate(all_records):
        if i < j:  # To avoid duplicate checks
            conditions1 = set(get_conditions(record1))
            conditions2 = set(get_conditions(record2))

            common_conditions = conditions1 & conditions2
            if common_conditions:
                edge_label = ", ".join(common_conditions)
                nt.add_edge(str(record1["_id"]), str(record2["_id"]), title=edge_label)


# Step 1: Convert pyvis network to a networkx graph
# Convert pyvis network to networkx graph
G = nx.Graph()
for node in nt.nodes:
    G.add_node(node["id"], label=node["label"])
for edge in nt.edges:
    G.add_edge(edge["from"], edge["to"], title=edge["title"])

partition = community_louvain.best_partition(G)
clusters = []
unique_partitions = set(partition.values())
for com in unique_partitions:
    list_nodes = [nodes for nodes in partition.keys() if partition[nodes] == com]
    clusters.append(set(list_nodes))

# Step 3 and 4: Add title nodes without specifying centroid
for idx, cluster in enumerate(clusters):
    # Determine all conditions for this cluster
    all_conditions = get_all_conditions_for_cluster(cluster, nt)
    formatted_conditions = insert_line_breaks(", ".join(all_conditions))
    cluster_label = formatted_conditions or f"Cluster {idx + 1}"

    if "Cluster" not in cluster_label:
        nt.add_node(
            cluster_label,
            shape="box",
            color="red",
            title=cluster_label,
            size=50,
        )

        # Connect the cluster title node to each node in the cluster using invisible edges
        for node_id in cluster:
            nt.add_edge(
                cluster_label, node_id, width=0, hidden=True
            )  # 'hidden=True' makes the edge invisible


# Save the graph as an HTML file
nt.save_graph("graph.html")

print("Graph saved as graph.html. Open this file in a web browser to view the graph.")

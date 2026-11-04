class Record:
    def __init__(self, record_id, parent_id):
        self.record_id = record_id
        self.parent_id = parent_id


class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.children = []


def BuildTree(records):
    """Build a tree of Nodes from a list of Records.

    Returns the root Node, or None when given an empty list.
    Raises ValueError for malformed input.
    """
    if not records:
        return None

    ordered = sorted(records, key=lambda record: record.record_id)
    ordered_ids = [record.record_id for record in ordered]
    if ordered_ids != list(range(len(ordered_ids))):
        raise ValueError("Record id is invalid or out of order.")

    nodes = {}
    root = None
    for record in ordered:
        if record.parent_id > record.record_id:
            raise ValueError("Node parent_id should be smaller than it's record_id.")
        if record.record_id != 0 and record.parent_id == record.record_id:
            raise ValueError("Only root should have equal record and parent id.")

        node = Node(record.record_id)
        nodes[node.node_id] = node

        if record.record_id == record.parent_id:
            root = node
        else:
            nodes[record.parent_id].children.append(node)

    return root

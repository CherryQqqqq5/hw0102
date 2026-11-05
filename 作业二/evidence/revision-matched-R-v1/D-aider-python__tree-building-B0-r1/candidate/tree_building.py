class Record:
    def __init__(self, record_id, parent_id):
        self.record_id = record_id
        self.parent_id = parent_id


class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.children = []


def BuildTree(records):
    """Reconstruct a tree from flat (record_id, parent_id) records.

    Returns the root Node, or None for an empty record set. Raises
    ValueError with a descriptive message when the input is not a valid
    tree.
    """
    if not records:
        return None

    records.sort(key=lambda record: record.record_id)
    if [record.record_id for record in records] != list(range(len(records))):
        raise ValueError("Record id is invalid or out of order.")

    nodes = [Node(node_id) for node_id in range(len(records))]
    root = None

    for record in records:
        node = nodes[record.record_id]
        if record.record_id == 0:
            if record.parent_id != 0:
                raise ValueError(
                    "Node parent_id should be smaller than it's record_id."
                )
            root = node
        elif record.record_id == record.parent_id:
            raise ValueError("Only root should have equal record and parent id.")
        elif record.record_id < record.parent_id:
            raise ValueError(
                "Node parent_id should be smaller than it's record_id."
            )
        else:
            nodes[record.parent_id].children.append(node)

    return root

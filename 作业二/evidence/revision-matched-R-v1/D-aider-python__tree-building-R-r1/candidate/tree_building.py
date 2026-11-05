class Record:
    def __init__(self, record_id, parent_id):
        self.record_id = record_id
        self.parent_id = parent_id


class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.children = []


def BuildTree(records):
    """Reconstruct a tree from a set of (record_id, parent_id) records.

    Returns the root Node, or None for an empty record list. Raises
    ValueError with a meaningful message for invalid input.
    """
    if not records:
        return None

    ordered = sorted(records, key=lambda record: record.record_id)
    ordered_ids = [record.record_id for record in ordered]

    # IDs must be exactly 0..n-1: no gaps, no duplicates, root present.
    if ordered_ids != list(range(len(ordered))):
        raise ValueError("Record id is invalid or out of order.")

    nodes = {record_id: Node(record_id) for record_id in ordered_ids}

    for record in ordered:
        if record.parent_id < 0 or record.record_id < record.parent_id:
            raise ValueError(
                "Node parent_id should be smaller than it's record_id."
            )
        if record.record_id == record.parent_id:
            if record.record_id != 0:
                raise ValueError(
                    "Only root should have equal record and parent id."
                )
        else:
            nodes[record.parent_id].children.append(nodes[record.record_id])

    return nodes[0]

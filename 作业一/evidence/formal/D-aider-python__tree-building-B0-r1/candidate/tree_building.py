class Record:
    def __init__(self, record_id, parent_id):
        self.record_id = record_id
        self.parent_id = parent_id


class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.children = []


def BuildTree(records):
    """Reconstruct a tree from a set of records.

    Each record has a unique ``record_id`` in ``range(len(records))`` and a
    ``parent_id`` that is smaller than ``record_id``, except for the root
    record, whose ``parent_id`` equals its own ``record_id``.

    Returns the root ``Node``, or ``None`` for an empty record list.
    Raises ``ValueError`` when the input does not describe a valid tree.
    """
    if not records:
        return None

    records = sorted(records, key=lambda record: record.record_id)

    if [record.record_id for record in records] != list(range(len(records))):
        raise ValueError("Record id is invalid or out of order.")

    nodes = [Node(record.record_id) for record in records]

    for record in records:
        if record.record_id < record.parent_id:
            raise ValueError("Node parent_id should be smaller than it's record_id.")
        if record.record_id == record.parent_id and record.record_id != 0:
            raise ValueError("Only root should have equal record and parent id.")
        if record.record_id != 0:
            nodes[record.parent_id].children.append(nodes[record.record_id])

    return nodes[0]
